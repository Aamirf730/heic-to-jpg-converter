from flask import Flask, render_template, request, jsonify, send_file, session
import os
import uuid
from werkzeug.utils import secure_filename
import cv2
import numpy as np
import io
import base64
from datetime import datetime
import zipfile
import imageio

# Try to import imageio-ffmpeg for better format support
try:
    import imageio_ffmpeg
    print("✅ imageio-ffmpeg available for enhanced format support")
except ImportError:
    print("⚠️ imageio-ffmpeg not available, using basic imageio")
except Exception as e:
    print(f"❌ Error importing imageio-ffmpeg: {e}")

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
            # Try OpenCV first
            img = cv2.imread(session_data['file_path'])
            if img is not None:
                print(f"Opened image with OpenCV: {img.shape}, mode: {img.dtype}")
            else:
                raise Exception("OpenCV could not read the file")
        except Exception as open_error:
            print(f"Failed to open with OpenCV: {open_error}")
            # Try imageio for HEIC support
            try:
                img_array = imageio.imread(session_data['file_path'])
                # Convert to BGR format for OpenCV
                if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                    img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                elif len(img_array.shape) == 3 and img_array.shape[2] == 4:
                    img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                else:
                    img = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
                print(f"Opened HEIC with imageio: size: {img.shape}, mode: {img.dtype}")
            except Exception as imageio_error:
                print(f"Failed to open with imageio: {imageio_error}")
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
                        # Open the converted file with OpenCV
                        img = cv2.imread(temp_output.name)
                        print(f"Opened HEIC with sips: size: {img.shape}, mode: {img.dtype}")
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
        if img.shape[2] == 4: # Check for alpha channel
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) # Convert BGRA to BGR
            print(f"Converted from BGRA to BGR mode")
        elif img.shape[2] == 3: # Check for RGB
            pass # Already RGB
        elif img.shape[2] == 2: # Check for grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) # Convert grayscale to BGR
            print(f"Converted from grayscale to BGR mode")
        elif img.shape[2] == 1: # Check for single channel
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) # Convert single channel to BGR
            print(f"Converted from single channel to BGR mode")
        
        # Prepare output
        output_buffer = io.BytesIO()
        
        # Determine output format and quality
        if output_format == 'jpeg':
            img_encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
        elif output_format == 'png':
            img_encoded = cv2.imencode('.png', img, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1]
        elif output_format == 'webp':
            img_encoded = cv2.imencode('.webp', img, [cv2.IMWRITE_WEBP_QUALITY, 90])[1]
        else:
            img_encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
        
        output_buffer.write(img_encoded)
        output_buffer.seek(0)
        
        # Strip EXIF if requested (OpenCV automatically strips EXIF data)
        if strip_exif:
            # OpenCV automatically strips EXIF data when encoding, so we just re-encode
            output_buffer = io.BytesIO()
            if output_format == 'jpeg':
                img_encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
            elif output_format == 'png':
                img_encoded = cv2.imencode('.png', img, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1]
            elif output_format == 'webp':
                img_encoded = cv2.imencode('.webp', img, [cv2.IMWRITE_WEBP_QUALITY, 90])[1]
            else:
                img_encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
            
            output_buffer.write(img_encoded)
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