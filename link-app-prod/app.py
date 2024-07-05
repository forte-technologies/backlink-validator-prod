import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = app.logger

def has_significant_content(soup):
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    if main_content:
        text = main_content.get_text(separator=' ', strip=True)
    else:
        text = soup.get_text(separator=' ', strip=True)

    words = text.split()
    word_count = len(words)

    logger.info(f"Word count: {word_count}")
    return word_count > 300

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_links', methods=['POST'])
def check_links():
    urls = request.form['urls'].split()
    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    logger.info(f"Received request to check {len(urls)} URLs")

    results = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    for url in urls[:1000]:  # Limit to first 1000 URLs for safety
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url

        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            status_code = response.status_code
            if status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                has_content = has_significant_content(soup)
            else:
                has_content = False
        except requests.RequestException as e:
            logger.error(f"Error checking URL {url}: {str(e)}")
            status_code = 'Error'
            has_content = False

        results.append({
            'URL': url,
            'Status Code': status_code,
            'Has Significant Content': 'Yes' if has_content else 'No'
        })

    df = pd.DataFrame(results)

    # Calculate summary statistics
    total_links = len(results)
    valid_links = sum(1 for r in results if r['Status Code'] == 200)
    invalid_links = total_links - valid_links
    links_with_content = sum(1 for r in results if r['Has Significant Content'] == 'Yes')
    forbidden_links = sum(1 for r in results if r['Status Code'] == 403)

    summary = {
        'Total Links Analyzed': total_links,
        'Total Invalid Links': invalid_links,
        'Total Links Without Significant Content': total_links - links_with_content,
        'Total 403 Forbidden Errors': forbidden_links
    }

    # Convert DataFrame to CSV string
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_string = csv_buffer.getvalue()

    return jsonify({
        'summary': summary,
        'csv': csv_string
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run()