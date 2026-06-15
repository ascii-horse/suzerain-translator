from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import urllib.request
import json
import time
import threading
import re

RESPONSE_CACHE = {}
CACHE_LOCK = threading.Lock()
GOOGLE_NET_LOCK = threading.Lock()
LAST_GOOGLE_REQUEST_TIME = 0.0

def protect_all_tags(text):
    # Extracts raw Unity RichText tags and replaces them with numerical tokens [999XX]. This ensures that line breaks (\n) and paragraph structures remain intact.
    tag_map = {}
    tags = re.findall(r'<[^>]+>', text)
    protected_text = text
    
    for idx, tag in enumerate(tags):
        token = f"[999{idx:02d}]"
        tag_map[token] = tag
        protected_text = protected_text.replace(tag, token, 1)
        
    return protected_text, tag_map

def restore_all_tags(translated_text, tag_map):
    # Restores the original Unity RichText tags back into the translated text.
    for token, tag in tag_map.items():
        translated_text = translated_text.replace(token, tag)
    return translated_text

class GoogleOnlyTranslationBridge(BaseHTTPRequestHandler):
    
    def handle_core_translation(self, text_to_translate):
        # Handles the core translation logic, including caching, input filtering, tag isolation, and communication with the Google Translate API.
        global LAST_GOOGLE_REQUEST_TIME
        if not text_to_translate.strip():
            return ""

        # Thread-safe cache lookup
        with CACHE_LOCK:
            if text_to_translate in RESPONSE_CACHE:
                return RESPONSE_CACHE[text_to_translate]

        # Prevent infinite loops if the game engine feeds back translated text
        if re.search(r'[а-яА-ЯіІєЄїЇґҐ]', text_to_translate):
            return text_to_translate

        # Isolate layout tags before sending text to the API
        print(f"[Game]: {text_to_translate.replace('\n', ' ')}")
        protected_text, tag_map = protect_all_tags(text_to_translate)
        translated_text = text_to_translate

        # Secure connection to Google Translate with rate-limiting
        try:
            with GOOGLE_NET_LOCK:
                current_time = time.time()
                time_passed = current_time - LAST_GOOGLE_REQUEST_TIME
                if time_passed < 0.3:
                    time.sleep(0.3 - time_passed)
                LAST_GOOGLE_REQUEST_TIME = time.time()

            google_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=uk&dt=t&q=" + urllib.parse.quote(protected_text)
            req = urllib.request.Request(
                google_url, headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                raw_translation = "".join([part[0] for part in res_json[0] if part[0]])
                
                # Reconstruct original formatting
                translated_text = restore_all_tags(raw_translation, tag_map)
                # Apply vocabulary fixes (optionally)
                # translated_text = translated_text.replace("Америка", "Анріка")
                
                print(f"      └─> [Google]: {translated_text.replace('\n', ' ')}")
                
        except Exception as net_err:
            print(f" [!!] API Network Error: {net_err}")
            translated_text = text_to_translate

        # Save successful translation to cache
        if translated_text:
            with CACHE_LOCK:
                RESPONSE_CACHE[text_to_translate] = translated_text
                
        return translated_text

    def process_any_request(self, path, body_data=""):
        # Parses incoming HTTP parameters and structures response payload compatible with XUnity AutoTranslator.
        parsed_url = urllib.parse.urlparse(path)
        params = urllib.parse.parse_qs(parsed_url.query)
        
        if body_data:
            post_params = urllib.parse.parse_qs(body_data)
            for k, v in post_params.items():
                params[k] = params.get(k, []) + v

        text_to_translate = ""
        is_google_format = False

        if 'q' in params:
            text_to_translate = params['q'][0]
            is_google_format = True
        elif 'text' in params:
            text_to_translate = params['text'][0]
            is_google_format = False
        elif body_data and not body_data.startswith('f.req='):
            text_to_translate = body_data

        # Initialize fake TKK token verification endpoint
        if not text_to_translate.strip() and "translate_a/single" not in path:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"TKK='430675.2721564364';")
            return

        translated_text = self.handle_core_translation(text_to_translate)

        self.send_response(200)
        if is_google_format:
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            google_format = [[[translated_text, text_to_translate, None, None, 1]], None, "en"]
            self.wfile.write(json.dumps(google_format, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(translated_text.encode('utf-8'))

    def do_GET(self):
        self.process_any_request(self.path)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
        self.process_any_request(self.path, post_data)

    # Override to suppress default HTTP server spam in console
    def log_message(self, format, *args):
        return

if __name__ == '__main__':
    SERVER_ADDRESS = ('', 8500)
    httpd = HTTPServer(SERVER_ADDRESS, GoogleOnlyTranslationBridge)
    print("=== SUZERAIN TRANSLATION ===\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down.")
