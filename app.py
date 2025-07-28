from flask import Flask, render_template, request, jsonify, send_file, session
import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
import io
import base64
from datetime import datetime
import zipfile

# Import pillow_heif to enable HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    print("✅ HEIF opener registered successfully")
except ImportError:
    print("❌ Warning: pillow_heif not available. HEIC files may not be supported.")
except Exception as e:
    print(f"❌ Error registering HEIF opener: {e}")

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store conversion sessions
conversion_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    if not file.filename.lower().endswith(('.heic', '.heif')):
        return jsonify({'error': 'Invalid file type. Only HEIC/HEIF files are supported.'}), 400
    
    # Check file size
    if file.content_length and file.content_length > app.config['MAX_CONTENT_LENGTH']:
        return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 400
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Save file
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{session_id}_{filename}')
    file.save(file_path)
    
    # Initialize conversion session
    conversion_sessions[session_id] = {
        'file_path': file_path,
        'original_filename': filename,
        'status': 'pending',
        'progress': 0,
        'created_at': datetime.now()
    }
    
    return jsonify({
        'session_id': session_id,
        'filename': filename,
        'status': 'pending'
    })

@app.route('/convert', methods=['POST'])
def convert_file():
    data = request.get_json()
    session_id = data.get('session_id')
    strip_exif = data.get('strip_exif', False)
    output_format = data.get('output_format', 'jpeg')
    
    if session_id not in conversion_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session_data = conversion_sessions[session_id]
    
    try:
        # Update status to converting
        session_data['status'] = 'converting'
        session_data['progress'] = 10
        
        # Convert HEIC to target format
        print(f"Attempting to open file: {session_data['file_path']}")
        print(f"File exists: {os.path.exists(session_data['file_path'])}")
        print(f"File size: {os.path.getsize(session_data['file_path'])} bytes")
        
        # Try to open the image
        img = None
        try:
            img = Image.open(session_data['file_path'])
            print(f"Opened image: {img.format}, size: {img.size}, mode: {img.mode}")
        except Exception as open_error:
            print(f"Failed to open with default method: {open_error}")
            # Try alternative method for HEIC with different parameters
            try:
                import pillow_heif
                heif_file = pillow_heif.read_heif(session_data['file_path'], convert_hdr_to_8bit=True)
                img = Image.frombytes(
                    heif_file.mode, 
                    heif_file.size, 
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
                print(f"Opened HEIC with pillow_heif: size: {img.size}, mode: {img.mode}")
            except Exception as heif_error:
                print(f"Failed to open with pillow_heif: {heif_error}")
                # Try one more approach with different parameters
                try:
                    heif_file = pillow_heif.read_heif(session_data['file_path'], convert_hdr_to_8bit=True, bgr_mode=False)
                    img = Image.frombytes(
                        heif_file.mode, 
                        heif_file.size, 
                        heif_file.data,
                        "raw",
                        heif_file.mode,
                        heif_file.stride,
                    )
                    print(f"Opened HEIC with pillow_heif (alternative): size: {img.size}, mode: {img.mode}")
                except Exception as heif_error2:
                    print(f"Failed to open with pillow_heif (alternative): {heif_error2}")
                    # Try using macOS sips as final fallback
                    try:
                        import subprocess
                        import tempfile
                        
                        # Create a temporary file for the converted image
                        temp_output = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                        temp_output.close()
                        
                        # Use sips to convert HEIC to JPEG
                        result = subprocess.run([
                            'sips', '-s', 'format', 'jpeg', 
                            session_data['file_path'], 
                            '--out', temp_output.name
                        ], capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            # Open the converted file with Pillow
                            img = Image.open(temp_output.name)
                            print(f"Opened HEIC with sips: size: {img.size}, mode: {img.mode}")
                            # Clean up temp file
                            os.unlink(temp_output.name)
                        else:
                            print(f"sips conversion failed: {result.stderr}")
                            raise open_error
                    except Exception as sips_error:
                        print(f"Failed to open with sips: {sips_error}")
                        raise open_error
        
        if img is None:
            return jsonify({'error': 'Failed to open image file'}), 500
        
        # Convert to RGB if necessary (handle various color modes)
        if img.mode not in ('RGB', 'L'):
            if img.mode in ('RGBA', 'LA', 'P', 'CMYK', 'YCbCr', 'LAB', 'HSV', 'I', 'F'):
                img = img.convert('RGB')
                print(f"Converted from {img.mode} to RGB mode")
            elif img.mode == 'L':
                # Grayscale - keep as is
                pass
            else:
                # For any other mode, convert to RGB
                img = img.convert('RGB')
                print(f"Converted from {img.mode} to RGB mode")
        
        # Prepare output
        output_buffer = io.BytesIO()
        
        # Determine output format and quality
        if output_format == 'jpeg':
            img.save(output_buffer, format='JPEG', quality=90, optimize=True)
        elif output_format == 'png':
            img.save(output_buffer, format='PNG', optimize=True)
        elif output_format == 'webp':
            img.save(output_buffer, format='WebP', quality=90, method=6)
        else:
            img.save(output_buffer, format='JPEG', quality=90, optimize=True)
        
        output_buffer.seek(0)
        
        # Strip EXIF if requested
        if strip_exif:
            # Create new image without EXIF
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(list(img.getdata()))
            
            output_buffer = io.BytesIO()
            if output_format == 'jpeg':
                img_without_exif.save(output_buffer, format='JPEG', quality=90, optimize=True)
            elif output_format == 'png':
                img_without_exif.save(output_buffer, format='PNG', optimize=True)
            elif output_format == 'webp':
                img_without_exif.save(output_buffer, format='WebP', quality=90, method=6)
            else:
                img_without_exif.save(output_buffer, format='JPEG', quality=90, optimize=True)
            
            output_buffer.seek(0)
        
        # Update session with converted data
        session_data['converted_data'] = output_buffer.getvalue()
        session_data['output_format'] = output_format
        session_data['status'] = 'completed'
        session_data['progress'] = 100
        
        print(f"Conversion completed successfully: {len(session_data['converted_data'])} bytes")
        
        response = jsonify({
            'status': 'completed',
            'progress': 100,
            'output_format': output_format
        })
        print("Returning success response")
        return response
        
    except Exception as e:
        print(f"Conversion error: {str(e)}")
        import traceback
        traceback.print_exc()
        session_data['status'] = 'error'
        session_data['error'] = str(e)
        return jsonify({'error': str(e)}), 500

@app.route('/download/<session_id>')
def download_file(session_id):
    if session_id not in conversion_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session_data = conversion_sessions[session_id]
    
    if session_data['status'] != 'completed':
        return jsonify({'error': 'File not ready for download'}), 400
    
    # Generate filename
    base_name = os.path.splitext(session_data['original_filename'])[0]
    extension = session_data['output_format']
    if extension == 'jpeg':
        extension = 'jpg'
    
    filename = f'{base_name}.{extension}'
    
    # Create file-like object
    file_data = io.BytesIO(session_data['converted_data'])
    
    return send_file(
        file_data,
        as_attachment=True,
        download_name=filename,
        mimetype=f'image/{session_data["output_format"]}'
    )

@app.route('/status/<session_id>')
def get_status(session_id):
    if session_id not in conversion_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session_data = conversion_sessions[session_id]
    return jsonify({
        'status': session_data['status'],
        'progress': session_data['progress'],
        'error': session_data.get('error'),
        'output_format': session_data.get('output_format')
    })

@app.route('/clear/<session_id>', methods=['DELETE'])
def clear_session(session_id):
    if session_id in conversion_sessions:
        # Remove file
        try:
            os.remove(conversion_sessions[session_id]['file_path'])
        except:
            pass
        
        # Remove session
        del conversion_sessions[session_id]
        
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port) 