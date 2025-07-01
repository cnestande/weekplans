# PDF & Screensaver Dashboard

A Flask-based web application designed for a Raspberry Pi or similar device to display rotating weekly schedules and a screensaver. It features a simple admin panel to manage content and settings.

**Documentation is limited!**

## Features

- **Dual Weekplan Display**: Shows two separate weekly schedules, which are updated by uploading PDF files.
- **Image Screensaver**: Displays a slideshow of images from a designated folder when the main dashboard is not active.
- **Web-based Admin Panel**: An easy-to-use interface to:
  - Upload new weekplan PDFs.
  - Upload screensaver images from a local file or a URL.
  - Activate or deactivate specific screensaver images.
  - Configure weekplan names and icons.
  - View system status (CPU, memory, disk usage).
  - Control the display and system (requires MQTT integration).
- **MQTT Integration (Optional)**: Can be configured to connect to an MQTT broker for remote control, perfect for home automation systems like Home Assistant.
- **Responsive Layout**: The main dashboard automatically adjusts its layout for both landscape and portrait/square displays.

## File Structure

```
.
├── app.py                  # Main Flask application
├── config.json             # Stores all application settings
├── last_updates.json       # Tracks when weekplans were last updated
├── requirements.txt        # Python dependencies
├── LICENSE                 # The software license
├── static/
│   ├── images/             # Stores the converted weekplan PNGs
│   ├── js/
│   │   ├── admin.js        # JavaScript for the admin panel
│   │   └── dashboard.js    # JavaScript for the main dashboard
│   └── screensaver/        # Stores screensaver images
├── uploads/                # Stores the uploaded PDFs
└── templates/
    ├── admin.html          # Admin panel template
    └── dashboard.html      # Main dashboard template
```
