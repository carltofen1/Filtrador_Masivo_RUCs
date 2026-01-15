
import requests
import json
import re

class DebugLogin:
    BASE_URL = "https://transforma.my.site.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1"
        })
        self.username = "usuario1h&gsolucionesdenegocios@claro.comunidad.com"
        self.password = "Hgsoluciones2025+"
        self.fwuid = None
        self.aura_token = None
        self.context_loaded = None

    def _extract_tokens(self, html):
        fwuid = re.search(r'"fwuid"\s*:\s*"([^"]+)"', html)
        if fwuid: self.fwuid = fwuid.group(1)
        
        token = re.search(r'"token"\s*:\s*"([^"]+)"', html)
        if token: self.aura_token = token.group(1)

        # Extract context loaded
        loaded_match = re.search(r'"loaded"\s*:\s*({[^}]+})', html)
        if loaded_match:
            try:
                self.context_loaded = json.loads(loaded_match.group(1))
            except:
                pass

    def run(self):
        print("1. GET Login Page...")
        r = self.session.get(f"{self.BASE_URL}/s/login/")
        print(f"   Status: {r.status_code}, Size: {len(r.text)}")
        self._extract_tokens(r.text)
        print(f"   FWUID: {self.fwuid}")
        print(f"   Loaded: {self.context_loaded}")
        print(f"   Cookies: {self.session.cookies.get_dict()}")

        if not self.fwuid: return

        # Try Variations
        variations = [
            ("Standard", {"Origin": self.BASE_URL, "Referer": f"{self.BASE_URL}/s/login/"}, "undefined"),
            ("Browser Mimic", {
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/s/login/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": "XMLHttpRequest" 
            }, "undefined"),
             ("Empty Token String", {}, ""),
        ]

        for name, extra_headers, token_val in variations:
            print(f"\n--- Testing Variation: {name} ---")
            
            # Use EXACTLY what was in the page
            loaded_ctx = self.context_loaded or {"APPLICATION@markup://siteforce:loginApp2": "1343_FXfywJTDy_Pq6QSlM3hWkA"}

            context = {
                "mode": "PROD",
                "fwuid": self.fwuid,
                "app": "siteforce:loginApp2",
                "loaded": loaded_ctx,
                "dn": [], "globals": {}, "uad": False
            }
            
            actions = [{
                "id": "214;a",
                "descriptor": "apex://LightningLoginFormController/ACTION$login",
                "callingDescriptor": "markup://c:loginForm",
                "params": {
                    "username": self.username,
                    "password": self.password,
                    "startUrl": "/s/"
                }
            }]

            data = {
                "message": json.dumps({"actions": actions}),
                "aura.context": json.dumps(context),
                "aura.pageURI": "/s/login/",
                "aura.token": token_val
            }
            
            headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
            headers.update(extra_headers)

            # Preparar request para inspeccionar body
            req = requests.Request('POST', f"{self.BASE_URL}/s/sfsites/aura", data=data, headers=headers, params={"r": 3, "apex.LightningLoginFormController.login": 1})
            prepped = self.session.prepare_request(req)
            
            print(f"   Request Body Preview: {prepped.body[:200]}...")

            r = self.session.send(prepped, timeout=30)
            
            try:
                resp_json = r.json()
                actions_resp = resp_json.get("actions", [])
                print(f"   Actions count: {len(actions_resp)}")
                if actions_resp:
                    print("   SUCCESS! Variation works.")
                    for a in actions_resp:
                        print(f"   State: {a.get('state')}")
                        print(f"   ReturnValue: {a.get('returnValue')}")
                    return # Stop on first success
            except Exception as e:
                print(f"   Error: {e}")
                print(f"   Response Text: {r.text[:200]}")

if __name__ == "__main__":
    DebugLogin().run()
