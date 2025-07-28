# HEIC to JPG Converter

A modern, privacy-first HEIC to JPG converter built with Python Flask. This application allows users to convert HEIC/HEIF images to JPEG, PNG, or WebP formats with a beautiful, responsive design.

## Features

- **Privacy First**: Files are converted on the server and immediately deleted after processing
- **Multiple Formats**: Convert to JPEG, PNG, or WebP
- **EXIF Stripping**: Optional removal of metadata for enhanced privacy
- **Drag & Drop**: Intuitive file upload interface
- **Progress Tracking**: Real-time conversion progress
- **Batch Processing**: Convert multiple files at once
- **Modern UI**: Beautiful, responsive design with Tailwind CSS
- **Error Handling**: Comprehensive error reporting and recovery

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd heic-to-jpg-python
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and navigate to `http://localhost:5000`

3. **Upload HEIC files** by dragging and dropping or clicking the upload area

4. **Configure settings**:
   - Choose output format (JPEG, PNG, WebP)
   - Toggle EXIF data stripping for privacy

5. **Download converted files** individually or in batch

## Technical Details

### Backend (Flask)
- **Framework**: Flask 3.0.0
- **Image Processing**: Pillow with pillow-heif extension
- **File Handling**: Werkzeug for secure file uploads
- **Session Management**: In-memory session storage for file processing

### Frontend
- **Styling**: Tailwind CSS (CDN)
- **Interactions**: Vanilla JavaScript
- **Design**: Identical to the original React application

### File Structure
```
heic-to-jpg-python/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   └── index.html        # Main HTML template
├── static/
│   └── js/
│       └── app.js        # Frontend JavaScript
└── uploads/              # Temporary file storage (auto-created)
```

### API Endpoints

- `GET /` - Main application page
- `POST /upload` - Upload HEIC file
- `POST /convert` - Convert uploaded file
- `GET /download/<session_id>` - Download converted file
- `GET /status/<session_id>` - Get conversion status
- `DELETE /clear/<session_id>` - Clear session and delete files

## Configuration

### Environment Variables
- `FLASK_ENV`: Set to `development` for debug mode
- `UPLOAD_FOLDER`: Custom upload directory (default: `uploads`)
- `MAX_CONTENT_LENGTH`: Maximum file size in bytes (default: 16MB)

### File Size Limits
- Maximum file size: 10MB per file
- Supported formats: HEIC, HEIF
- Output formats: JPEG, PNG, WebP

## Security Features

- **File Validation**: Strict file type checking
- **Secure Filenames**: Automatic filename sanitization
- **Session Management**: Unique session IDs for each file
- **Automatic Cleanup**: Files deleted after processing
- **EXIF Stripping**: Optional metadata removal

## Browser Compatibility

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## Development

### Running in Development Mode
```bash
export FLASK_ENV=development
python app.py
```

### Testing
The application includes comprehensive error handling and validation:
- File type validation
- File size limits
- Network error handling
- Conversion error recovery

## Deployment

### Production Setup
1. Use a production WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

2. Set up a reverse proxy (nginx/Apache) for static file serving

3. Configure proper file permissions for the uploads directory

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p uploads

EXPOSE 5000
CMD ["python", "app.py"]
```

## License

This project is open source and available under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions, please open an issue on the GitHub repository.
