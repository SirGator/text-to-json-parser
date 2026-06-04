from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.api.routes import router

app = FastAPI(title="Text2JSON API", version="0.2.0")

# CORS ist an, damit der ARCS interpretation_worker (oder das Web-UI)
# auch cross-origin anfragen darf. Lokale Entwicklungsumgebung.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
    <!doctype html>
    <html lang="de">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Text to JSON</title>
      <style>
        :root { color-scheme: dark; }
        body {
          margin: 0;
          font-family: system-ui, sans-serif;
          background: #0f172a;
          color: #e2e8f0;
        }
        .wrap {
          max-width: 1100px;
          margin: 0 auto;
          padding: 24px;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 16px;
        }
        .card {
          background: #111827;
          border: 1px solid #334155;
          border-radius: 14px;
          padding: 16px;
        }
        label {
          display: block;
          font-size: 14px;
          margin-bottom: 8px;
          color: #cbd5e1;
        }
        textarea {
          width: 100%;
          min-height: 260px;
          box-sizing: border-box;
          padding: 12px;
          border-radius: 10px;
          border: 1px solid #475569;
          background: #0b1220;
          color: #e2e8f0;
          resize: vertical;
          font: inherit;
        }
        textarea[readonly] { opacity: 0.95; }
        .actions {
          display: flex;
          gap: 12px;
          align-items: center;
          margin: 16px 0;
        }
        button {
          border: 0;
          border-radius: 10px;
          padding: 12px 18px;
          background: #38bdf8;
          color: #082f49;
          font-weight: 700;
          cursor: pointer;
        }
        .status {
          color: #93c5fd;
          font-size: 14px;
        }
        h1 { margin: 0 0 16px; font-size: 28px; }
        p { margin: 0 0 20px; color: #94a3b8; }
      </style>
    </head>
    <body>
      <div class="wrap">
        <h1>Text to JSON</h1>
        <p>Text, Prompt und Schema eingeben und JSON per API erzeugen lassen.</p>

        <div class="actions">
          <button id="generateBtn">JSON erzeugen</button>
          <div id="status" class="status">Bereit</div>
        </div>

        <div class="grid">
          <div class="card">
            <label for="textInput">1. Text</label>
            <textarea id="textInput" placeholder="Freitext hier eingeben">Max Mustermann ist 32 Jahre alt und wohnt in Berlin.</textarea>
          </div>

          <div class="card">
            <label for="schemaInput">2. Schema</label>
            <textarea id="schemaInput" placeholder='JSON Schema hier eingeben'>{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "age": { "type": "integer" },
    "city": { "type": "string" }
  },
  "required": ["name", "age", "city"],
  "additionalProperties": false
}</textarea>
          </div>

          <div class="card">
            <label for="promptInput">3. Prompt</label>
            <textarea id="promptInput" placeholder="Optionalen Prompt mit Platzhaltern wie {text} oder {schema} eingeben"></textarea>
          </div>

          <div class="card">
            <label for="outputInput">4. JSON Output</label>
            <textarea id="outputInput" readonly placeholder="Hier erscheint das JSON"></textarea>
          </div>
        </div>
      </div>

      <script>
        const statusEl = document.getElementById('status');
        const outputEl = document.getElementById('outputInput');
        const generateBtn = document.getElementById('generateBtn');
        const promptEl = document.getElementById('promptInput');

        async function generateJson() {
          statusEl.textContent = 'Lade...';
          outputEl.value = '';

          let schema;
          try {
            schema = JSON.parse(document.getElementById('schemaInput').value);
          } catch (error) {
            statusEl.textContent = 'Schema ist kein gültiges JSON';
            outputEl.value = String(error);
            return;
          }

          const response = await fetch('/generate-json', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: document.getElementById('textInput').value,
              schema,
              prompt: promptEl.value,
            })
          });

          const result = await response.json();

          if (!response.ok || result.ok === false) {
            statusEl.textContent = 'Fehler';
            outputEl.value = JSON.stringify(result, null, 2);
            return;
          }

          statusEl.textContent = 'Fertig';
          outputEl.value = JSON.stringify(result.data, null, 2);
        }

        generateBtn.addEventListener('click', () => {
          generateJson().catch((error) => {
            statusEl.textContent = 'Fehler beim Laden';
            outputEl.value = String(error);
          });
        });
      </script>
    </body>
    </html>
    """
