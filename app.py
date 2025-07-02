import os
import pytesseract
from flask import Flask, render_template, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename
import re
from PIL import Image

OCR_LANGUAGES = 'chi_sim'
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# 我的tesseract.exe路径位置
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__, static_folder=STATIC_FOLDER)  # 指定 static_folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 上传限制

if not os.path.exists(os.path.join(STATIC_FOLDER, UPLOAD_FOLDER)):
    os.makedirs(os.path.join(STATIC_FOLDER, UPLOAD_FOLDER))


# 添加生成文件的路由映射
@app.route('/processed/<path:filename>')
def processed_files(filename):
    # 指向绝对路径
    processed_dir = r'C:\Users\wangqiang\PycharmProjects\ocr_demo\processed'
    return send_from_directory(processed_dir, filename)


def parse_bbox(title_string):
    """从title字符串中解析 'bbox x1 y1 x2 y2'"""
    match = re.search(r'bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', title_string)
    if match:
        return [int(c) for c in match.groups()]
    return None


def perform_ocr_web(pil_image):
    words_data = []
    try:
        hocr_output = pytesseract.image_to_pdf_or_hocr(pil_image, lang=OCR_LANGUAGES, extension='hocr')
        soup = BeautifulSoup(hocr_output, 'html.parser')

        global_idx = 0

        for line_idx, line_element in enumerate(soup.find_all('span', class_='ocr_line')):
            line_bbox = parse_bbox(line_element.get('title', ''))
            if not line_bbox:
                continue

            for word_idx, word_element in enumerate(line_element.find_all('span', class_='ocrx_word')):
                word_text = word_element.text
                word_bbox = parse_bbox(word_element.get('title', ''))
                if not word_text or not word_bbox:
                    continue
                x1, y1, x2, y2 = word_bbox
                js_box = [x1, y1, x2 - x1, y2 - y1]  # 转换为 [x, y, width, height]
                words_data.append({
                    'word': word_text.strip(),
                    'box': js_box,
                    'line_index': line_idx,
                    'word_index': word_idx,
                    'global_index': global_idx
                })
                global_idx += 1
        words_data.sort(key=lambda c: c['global_index'])
        return words_data

    except pytesseract.TesseractNotFoundError:
        raise Exception("Tesseract is not installed or not found in your PATH.")
    except Exception as e:
        print(f"Error during OCR or parsing: {e}")
        raise Exception(f"An error occurred during OCR: {str(e)}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_image():
    """处理图片上传和OCR识别"""
    if 'file' not in request.files:
        return jsonify(success=False, error="No file part")

    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, error="No selected file")

    try:
        # 保存原始文件
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 使用PIL打开图片进行OCR
        img = Image.open(filepath)
        words_data = perform_ocr_web(img)

        # 处理后的图像
        processed_filename = f"processed_{filename}"


        # 返回结果
        return jsonify(
            success=True,
            imageUrl=f"/processed/{processed_filename}",
            ocrData=words_data
        )

    except Exception as e:
        app.logger.error(f"OCR  processing error: {str(e)}")
        return jsonify(success=False, error=str(e))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """返回已上传的图片文件"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return "File not found", 404


if __name__ == '__main__':
    # print(pytesseract.pytesseract.tesseract_cmd)
    app.run(debug=True, host='0.0.0.0', port=5001)
