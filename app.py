import os, threading, uuid, time, random
import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template, render_template_string
from flask_cors import CORS
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from pyngrok import ngrok
import requests

app = Flask(__name__, template_folder='.')
CORS(app)
os.makedirs('scrape_outputs', exist_ok=True)
jobs = {}

def scrape_amazon(search_query, max_pages=1):
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = uc.Chrome(options=options)

    base_url = f'https://www.amazon.in/s?k={search_query.replace(" ", "+")}'
    results = []

    for page in range(1, max_pages + 1):
        driver.get(f'{base_url}&page={page}')
        time.sleep(random.uniform(5, 8))
        soup = BeautifulSoup(driver.page_source, 'lxml')
        items = soup.select("div.s-main-slot div[data-component-type='s-search-result']")
        for i in items:
            name = i.select_one('h2 a span')
            price = i.select_one('span.a-price-whole')
            rating = i.select_one('span.a-icon-alt')
            link = i.select_one('h2 a')
            if not name or not price: continue
            results.append({
                'Product Name': name.text.strip(),
                'Price (INR)': price.text.replace(',', '').strip(),
                'Rating': rating.text.strip() if rating else 'N/A',
                'Product Link': f'https://www.amazon.in{link["href"]}' if link else 'N/A'
            })

    driver.quit()
    df = pd.DataFrame(results)
    filename = f'scrape_outputs/{search_query.replace(" ", "_")}_{uuid.uuid4().hex[:6]}.csv'
    df.to_csv(filename, index=False)
    return filename, len(results)

def run_scrape_job(job_id, query, pages):
    jobs[job_id]['status'] = 'running'
    try:
        file, count = scrape_amazon(query, pages)
        jobs[job_id].update({'status': 'done', 'file': file, 'message': f'Scraped {count} products'})
    except Exception as e:
        jobs[job_id].update({'status': 'error', 'message': str(e)})

@app.route('/start_scrape', methods=['POST'])
def start_scrape():
    data = request.json
    query = data.get('search_query', '')
    pages = int(data.get('max_pages', 1))
    if not query:
        return jsonify({'error': 'search_query required'}), 400
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'pending', 'message': 'Queued'}
    threading.Thread(target=run_scrape_job, args=(job_id, query, pages), daemon=True).start()
    return jsonify({'job_id': job_id, 'status_url': f'/status/{job_id}', 'download_url': f'/download/{job_id}'})

@app.route('/status/<job_id>')
def check_status(job_id):
    return jsonify(jobs.get(job_id, {'error': 'job not found'}))

@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'done':
        return jsonify({'error': 'not ready'}), 404
    return send_file(job['file'], as_attachment=True)

@app.route('/')
def home():
    return render_template('scraper_ui.html')

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

ngrok.set_auth_token("34GxjdqiHV8B21mthplg91usTPc_wjdDVDHbF1aoEyMBseRK")
print("✅ Ngrok authentication set successfully!")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>💻 Amazon Laptop Scraper</title>
<style>
    body {
        font-family: 'Segoe UI', sans-serif;
        background: linear-gradient(135deg,#4facfe,#00f2fe);
        color:#333;
        text-align:center;
        padding:30px;
    }
    h1 {
        color:#fff;
        text-shadow:1px 1px 3px #000;
    }
    form {
        margin-top:30px;
    }
    input[type=text] {
        width:280px; padding:10px; border:none;
        border-radius:6px; font-size:16px;
    }
    button {
        padding:10px 16px; border:none; border-radius:6px;
        background:#333; color:#fff; cursor:pointer;
        transition:0.3s;
    }
    button:hover { background:#555; }
    table {
        margin:30px auto; border-collapse:collapse;
        width:95%; max-width:1100px;
        background:white; border-radius:10px; overflow:hidden;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
    }
    th, td { padding:12px 15px; border-bottom:1px solid #ddd; vertical-align:middle; }
    th { background:#333; color:#fff; }
    tr:hover { background:#f1f1f1; }
    a { color:#007bff; text-decoration:none; }
    a:hover { text-decoration:underline; }
    img { width:100px; border-radius:8px; }
</style>
</head>
<body>
    <h1>💻 Amazon Laptop Scraper</h1>
    <form action="/scrape" method="post">
        <input type="text" name="query" placeholder="Enter laptop name (e.g. HP, Dell)" required>
        <button type="submit">🔍 Search</button>
    </form>
    {% if message %}
        <h3>{{ message|safe }}</h3>
    {% endif %}
    {% if products %}
        <h2>✅ Found {{ products|length }} products for '{{ query }}'</h2>
        <table>
            <tr><th>Image</th><th>Title</th><th>Price</th><th>Link</th></tr>
            {% for p in products %}
            <tr>
                <td><img src="{{ p.image }}" alt="Laptop Image"></td>
                <td>{{ p.title }}</td>
                <td>{{ p.price }}</td>
                <td><a href="{{ p.link }}" target="_blank">View</a></td>
            </tr>
            {% endfor %}
        </table>
        <a href="/download"><button>⬇ Download CSV</button></a>
    {% endif %}
</body>
</html>
"""

@app.route('/scrape', methods=['POST'])
def scrape():
    query = request.form.get('query')
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, message=f"❌ Error fetching data: {e}")

    soup = BeautifulSoup(res.text, "html.parser")
    products = []

    for item in soup.select("div[data-component-type='s-search-result']"):
        title = item.h2.text.strip() if item.h2 else "No title"
        price_elem = item.select_one("span.a-price-whole")
        price = price_elem.text.strip() if price_elem else "N/A"
        link = "https://www.amazon.in" + item.h2.a["href"] if item.h2 and item.h2.a else "#"
        img_tag = item.select_one("img.s-image")
        image = img_tag["src"] if img_tag and "src" in img_tag.attrs else ""
        products.append({"title": title, "price": price, "link": link, "image": image})

    if not products:
        return render_template_string(HTML_TEMPLATE, message=f"❌ No products found for '{query}'")

    df = pd.DataFrame(products)
    df.to_csv("amazon_results.csv", index=False, encoding='utf-8-sig')

    return render_template_string(HTML_TEMPLATE, products=products[:20], query=query)

@app.route('/download')
def download_csv():
    return send_file("amazon_results.csv", as_attachment=True)

# ---- Run Flask with ngrok in Colab ----
port = 5000
public_url = ngrok.connect(port).public_url
print(f"🌐 Open the web app here: {public_url}")
app.run(port=port)
