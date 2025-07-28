from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
import io
import zipfile
import tempfile
import subprocess
from werkzeug.utils import secure_filename
from PIL import Image
import pillow_heif

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Register HEIF opener
pillow_heif.register_heif_opener()
print("✅ HEIF opener registered successfully")

# Store session data in memory (in production, use a proper database)
sessions = {}

# Ensure uploads directory exists
os.makedirs('uploads', exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'.heic', '.heif', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Please upload an image file.'}), 400
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Save file
    filename = secure_filename(file.filename)
    file_path = os.path.join('uploads', f'{session_id}_{filename}')
    file.save(file_path)
    
    # Store session data
    sessions[session_id] = {
        'file_path': file_path,
        'original_filename': filename,
        'converted_path': None
    }
    
    return jsonify({'session_id': session_id, 'filename': filename})

@app.route('/convert', methods=['POST'])
def convert_file():
    data = request.get_json()
    session_id = data.get('session_id')
    quality = data.get('quality', 90)
    strip_exif = data.get('strip_exif', False)
    
    if session_id not in sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session_data = sessions[session_id]
    
    try:
        print(f"Attempting to open file: {session_data['file_path']}")
        print(f"File exists: {os.path.exists(session_data['file_path'])}")
        print(f"File size: {os.path.getsize(session_data['file_path'])} bytes")
        
        # Try to open the image
        img = None
        open_error = None
        
        try:
            # Try default method first
            img = Image.open(session_data['file_path'])
            print(f"Opened image: {img.format}, size: {img.size}, mode: {img.mode}")
        except Exception as e:
            print(f"Failed to open with default method: {e}")
            open_error = e
            
            # Try pillow_heif for HEIC files
            if session_data['file_path'].lower().endswith(('.heic', '.heif')):
                try:
                    heif_file = pillow_heif.read_heif(session_data['file_path'])
                    img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode, heif_file.stride)
                    print(f"Opened HEIC image: {img.size}, mode: {img.mode}")
                except Exception as heif_error:
                    print(f"Failed to open with pillow_heif: {heif_error}")
                    
                    # Try alternative pillow_heif method
                    try:
                        heif_file = pillow_heif.read_heif(session_data['file_path'], convert_hdr_to_8bit=True)
                        img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode, heif_file.stride)
                        print(f"Opened HEIC image (alternative): {img.size}, mode: {img.mode}")
                    except Exception as heif_error2:
                        print(f"Failed to open with pillow_heif (alternative): {heif_error2}")
                        
                        # Try macOS sips as last resort
                        try:
                            temp_jpg = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                            temp_jpg.close()
                            
                            result = subprocess.run(['sips', '-s', 'format', 'jpeg', session_data['file_path'], '--out', temp_jpg.name], 
                                                  capture_output=True, text=True, timeout=30)
                            
                            if result.returncode == 0:
                                img = Image.open(temp_jpg.name)
                                print(f"Opened HEIC image with sips: {img.size}, mode: {img.mode}")
                                # Clean up temp file
                                os.unlink(temp_jpg.name)
                            else:
                                print(f"sips failed: {result.stderr}")
                                raise Exception("All HEIC opening methods failed")
                        except Exception as sips_error:
                            print(f"sips method failed: {sips_error}")
                            raise open_error
        
        if img is None:
            raise open_error
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create a white background for transparent images
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Prepare output
        output_buffer = io.BytesIO()
        
        # Save as JPEG
        save_kwargs = {
            'format': 'JPEG',
            'quality': quality,
            'optimize': True
        }
        
        if strip_exif:
            # Create a new image without EXIF data
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(list(img.getdata()))
            img_without_exif.save(output_buffer, **save_kwargs)
        else:
            img.save(output_buffer, **save_kwargs)
        
        output_buffer.seek(0)
        
        # Save converted file
        converted_filename = os.path.splitext(session_data['original_filename'])[0] + '.jpg'
        converted_path = os.path.join('uploads', f'{session_id}_{converted_filename}')
        
        with open(converted_path, 'wb') as f:
            f.write(output_buffer.getvalue())
        
        # Update session data
        session_data['converted_path'] = converted_path
        
        print(f"Conversion completed successfully: {len(output_buffer.getvalue())} bytes")
        print("Returning success response")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'converted_filename': converted_filename,
            'file_size': len(output_buffer.getvalue())
        })
        
    except Exception as e:
        print(f"Conversion error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Conversion failed'}), 500

@app.route('/download/<session_id>')
def download_file(session_id):
    if session_id not in sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session_data = sessions[session_id]
    if not session_data.get('converted_path') or not os.path.exists(session_data['converted_path']):
        return jsonify({'error': 'Converted file not found'}), 404
    
    return send_file(
        session_data['converted_path'],
        as_attachment=True,
        download_name=os.path.basename(session_data['converted_path'])
    )

@app.route('/status/<session_id>')
def get_status(session_id):
    if session_id not in sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session_data = sessions[session_id]
    return jsonify({
        'session_id': session_id,
        'original_filename': session_data['original_filename'],
        'converted': session_data.get('converted_path') is not None
    })

@app.route('/clear/<session_id>', methods=['DELETE'])
def clear_session(session_id):
    if session_id in sessions:
        session_data = sessions[session_id]
        
        # Clean up files
        for file_path in [session_data['file_path'], session_data.get('converted_path')]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        
        # Remove session
        del sessions[session_id]
    
    return jsonify({'success': True})

@app.route('/sitemap.xml')
def sitemap():
    return send_file('static/sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_file('static/robots.txt', mimetype='text/plain')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False) 