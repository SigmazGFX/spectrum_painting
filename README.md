# sBitx Spectrogram Generator


This application allows you to convert text or images into spectrograms that can be transmitted via radio. It supports both a graphical user interface (GUI) and command-line operation.

## Table of Contents
- [Installation](#installation)
- [GUI Usage](#gui-usage)
- [Command-Line Usage](#command-line-usage)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites
- Python 3.x
- GTK 3.0
- sBitx DE,V2+, V3+ zBitx

### Dependencies
Install the required Python packages:

```bash
pip install -r requirements.txt
```

The requirements include:
- numpy
- Pillow
- progressbar33
- PyGObject
- pycairo

## GUI Usage

### Starting the Application
To start the application in GUI mode, simply run:

```bash
python3 spectrogram-generator.py
```

### Main Interface
The GUI provides the following features:

1. **Text Input**: Enter text to be converted to a spectrogram.
2. **Image Selection**: Alternatively, select an image file to convert.
3. **Transmission Controls**:
   - **Play Button**: Transmit the generated spectrogram.
   - **Clear Button**: Clear the current spectrogram.
4. **Visualization**:
   - A waterfall display shows the spectrogram as it's being transmitted.
5. **Settings**:
   - **Font Size**: Adjust the size of text (when using text input).
   - **Horizontal Flip**: Flip the image horizontally.
   - **Invert Colors**: Invert the colors of the spectrogram.
   - **Image Rotation**: Rotate the image by 0°, 90°, 180°, or 270°.
   - **TX Bandwidth**: Set minimum and maximum frequencies.

### Settings Dialog
Access additional settings by clicking the Settings button:
- Show/hide TX bandwidth controls
- Show/hide font size slider
- Show/hide horizontal flip control
- Show/hide invert control
- Toggle waterfall direction (top-down or bottom-up)

## Command-Line Usage

The application can be run from the command line with various options:

### Basic Usage
```bash
python3 spectrogram-generator.py --text "Hello World" --output spectrogram.wav
```

This generates a spectrogram WAV file without displaying the GUI.

### Transmitting from Command Line
To generate AND transmit in one command:

```bash
python3 spectrogram-generator.py --text "Hello World" --transmit
```

The application will:
1. Generate the spectrogram
2. Detect the current radio mode (USB/LSB)
3. Transmit the audio
4. Exit automatically when complete

### Available Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--text` | Text to convert to spectrogram | None |
| `--image` | Image file to convert to spectrogram | None |
| `--output` | Output WAV file | spectrogram.wav |
| `--font-size` | Font size for text | 50 |
| `--hflip` | Horizontally flip the image (0 or 1) | 0 |
| `--invert` | Invert the colors (0 or 1) | 1 |
| `--rotation` | Rotate the image (0, 90, 180, 270) | 0 |
| `--transmit` | Transmit the audio after generating | False |
| `--mode` | Force radio mode (USB or LSB) | Auto-detect |
| `--debug` | Enable debug output | Disabled |

### Examples

1. **Generate with custom font size**:
   ```bash
   python3 spectrogram-generator.py --text "Large Text" --font-size 75
   ```

2. **Generate from image and transmit**:
   ```bash
   python3 spectrogram-generator.py --image my_image.png --transmit
   ```

3. **Force LSB mode**:
   ```bash
   python3 spectrogram-generator.py --text "LSB Mode" --transmit --mode LSB
   ```

4. **Rotate image 90 degrees**:
   ```bash
   python3 spectrogram-generator.py --text "Rotated" --rotation 90 --transmit
   ```

5. **Generate with debug output**:
   ```bash
   python3 spectrogram-generator.py --text "Debug Test" --transmit --debug
   ```

6. **Suppress debug output (default behavior)**:
   ```bash
   python3 spectrogram-generator.py --text "No Debug" --transmit
   ```

## Advanced Features

### Debug Mode
The application includes a debug toggle feature that controls the verbosity of log output:

- By default, only important messages (INFO level and above) are displayed
- When running with the `--debug` flag, detailed debug information is shown
- This is useful for troubleshooting or development purposes

Example usage:
```bash
# Run with minimal output
python3 spectrogram-generator.py --text "Hello World" --transmit

# Run with detailed debug information
python3 spectrogram-generator.py --text "Hello World" --transmit --debug
```

### Radio Mode Detection
The application automatically detects the current radio mode (USB or LSB) when transmitting, ensuring correct orientation of the spectrogram. This works with radios that support Hamlib control.

### Hamlib Integration
The application connects to the *Bitx radio through the psudo Hamlib server running on localhost port 4532. This allows it to query the radio's current mode and adapt the spectrogram accordingly.

## Troubleshooting

### Hamlib Connection Issues
If you see "Failed to connect to Hamlib server" messages:
1. Ensure the sBitx application is running
2. Check that port 4532 is accessible
3. Use the `--mode` argument to manually specify the mode if auto-detection fails

### GTK Initialization Failed
If you see "GTK initialization failed" when running in command-line mode:
1. Ensure the DISPLAY environment variable is set correctly
2. Install required GTK libraries: `apt-get install libgtk-3-0`
