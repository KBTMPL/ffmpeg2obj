# ffmpeg2obj

With this tool you can easily automate conversion of your blu ray library and its upload to object storage.

## Installation

Have ffmpeg installed locally and available in PATH. You can install it from package manager or compile from source if you want to use hevc_nvenc codec (for example).

Clone repository

```bash
~$ git clone git@github.com:KBTMPL/ffmpeg2obj.git
~$ cd ffmpeg2obj
```

Setup and activate venv

```bash
~/ffmpeg2obj$ python3 -m venv venv
~/ffmpeg2obj$ source venv/bin/activate
```

Install the packages

For usage:

```bash
(venv) ~/ffmpeg2obj$ pip install .
```

For development:

```bash
(venv) ~/ffmpeg2obj$ pip install -e .[dev]
```

## Usage

### Environment setup

Provide your object storage credentials and endpoint in `.envrc` file, load it with *direnv* or just export those variables. You can use `.envrc.example` as a template.

```bash
(venv) ~/ffmpeg2obj$ cat .envrc.example
#!/bin/bash
export aws_access_key_id="";
export aws_secret_access_key="";
export endpoint_url="";
(venv) ~/ffmpeg2obj$
```

### Tool usage

The built-in help provides handles and default values for implemented functions

```bash
(venv) ~/ffmpeg2obj$ ffmpeg2obj --help
usage: ffmpeg2obj [-h] [-v] [--noop] [--force-cleanup] [-s SRC_DIR] [-d DST_DIR] [-i IGNORED_SUBDIR] [-o OBJ_PREFIX]
                  [--source-file-extension SOURCE_FILE_EXTENSION] [-e FILE_EXTENSION] [-vc VIDEO_CODEC] [--pix-fmt PIX_FMT]
                  [-l LANGS] [--width TARGET_WIDTH] [--resize] [--concat] [--height TARGET_HEIGHT]
                  (-b BUCKET_NAME | --disable-upload) [-qp TARGET_QP | -crf TARGET_CRF]

Simple tool to compress blu ray movie library and store it in obj

options:
  -h, --help            show this help message and exit
  -v, --verbose         show additional information
  --noop                script executes but takes no action
  --force-cleanup       cleans up even on upload failure
  -s SRC_DIR, --source-dir SRC_DIR
                        source directory for media to be transcoded
  -d DST_DIR, --destination-dir DST_DIR
                        temporary directory for media to be transcoded
  -i IGNORED_SUBDIR, --ignored-subdir IGNORED_SUBDIR
                        ignored subdirectories
  -o OBJ_PREFIX, --obj-prefix OBJ_PREFIX
                        source directory for media to be transcoded
  --source-file-extension SOURCE_FILE_EXTENSION
                        source extension for the media files to be transcoded
  -e FILE_EXTENSION, --file-extension FILE_EXTENSION
                        target extension for the media files to be transcoded
  -vc VIDEO_CODEC, --video-codec VIDEO_CODEC
                        video codec for transcoding of the media files
  --pix-fmt PIX_FMT     pix fmt for transcoding of the media files
  -l LANGS, --languages LANGS
                        selected languages transcoding of the media files, all keeps every track
  --width TARGET_WIDTH  target width for the media files to be transcoded
  --resize              scale input files to height x width
  --concat              concatenates files within same directory
  --height TARGET_HEIGHT
                        target height for the media files to be transcoded
  -b BUCKET_NAME, --bucket-name BUCKET_NAME
                        target bucket name to which output files will be uploaded
  --disable-upload      disables default upload to object storage and stores files locally
  -qp TARGET_QP         Quantization Parameter for the media files to be transcoded
  -crf TARGET_CRF       Constant Rate Factor for the media files to be transcoded
(venv) ~/ffmpeg2obj$
```
