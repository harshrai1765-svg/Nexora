async function performLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const error = document.getElementById("loginError");

  error.textContent = "";

  if (!username || !password) {
    error.textContent = "Please enter username and password.";
    return;
  }

  try {
    const response = await fetch(`${API}/login`, {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        username: username,
        password: password,
      }),
    });

    const text = await response.text();

    let data;

    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text || "Server returned an invalid response.");
    }

    if (!response.ok) {
      throw new Error(data.detail || "Login failed");
    }

    token = data.access_token;

    document.getElementById("loginScreen").style.display = "none";
    document.getElementById("dashboard").style.display = "flex";

    document.getElementById("loggedUser").textContent = data.username;

    await loadDashboardStats();
    await loadCaseData();
    await loadDocumentData();
    await loadIntegrityStatus();
    await loadAuditActivity();
  } catch (err) {
    error.textContent = err.message || "Unable to connect to Nexora.";
  }
}

let token = null;

const API =
  window.location.protocol === "file:"
    ? "http://127.0.0.1:8000"
    : window.location.origin;

document.addEventListener("DOMContentLoaded", () => {
  console.log("Nexora frontend ready.");

  if (typeof setupUpload === "function") {
    setupUpload();
  }

  if (typeof setupReportButton === "function") {
    setupReportButton();
  }
});

/* =========================
   LOGIN
========================= */

async function login(username, password) {
  const response = await fetch(`${API}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      username: username,
      password: password,
    }),
  });

  const text = await response.text();
  let data;

  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(text || "Server returned an invalid response.");
  }

  if (!response.ok) {
    throw new Error(data.detail || "Login failed");
  }

  return data;
}

/* =========================
   API REQUEST
========================= */

async function apiRequest(url, options = {}) {
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API}${url}`, {
    ...options,
    headers: headers,
  });

  const text = await response.text();

  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || "Server returned an invalid response.");
  }

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}
/* =========================
   LOAD CASE DATA
========================= */

async function loadCaseData() {
  try {
    const result = await apiRequest("/cases");

    if (!result.cases || result.cases.length === 0) {
      return;
    }

    const caseData = result.cases[0];

    const caseNumber = document.querySelector(".case-info .info-row strong");

    const caseTitle = document.querySelector(".section-heading h3");

    if (caseNumber) {
      caseNumber.textContent = caseData.case_number;
    }

    if (caseTitle) {
      caseTitle.textContent = caseData.title;
    }
  } catch (error) {
    console.error("Case data failed:", error);
  }
}

/* =========================
   LOAD DOCUMENT DATA
========================= */

async function loadDocumentData() {
  try {
    const cases = await apiRequest("/cases");

    if (!cases.cases || cases.cases.length === 0) {
      return;
    }

    const caseId = cases.cases[0].id;

    const result = await apiRequest(`/cases/${caseId}/documents`);

    if (!result.documents || result.documents.length === 0) {
      return;
    }

    const docData = result.documents[0];

    const name = document.querySelector(".document-main strong");

    const info = document.querySelector(".document-main span");

    const hash = document.querySelector(".document-hash code");

    if (name) {
      name.textContent = docData.filename;
    }

    if (info) {
      info.textContent = `${docData.document_type} · Version ${docData.current_version}`;
    }

    if (hash) {
      hash.textContent = docData.current_hash.substring(0, 16) + "...";
    }
  } catch (error) {
    console.error("Document data failed:", error);
  }
}

/* =========================
   LOAD INTEGRITY STATUS
========================= */

async function loadIntegrityStatus() {
  try {
    const cases = await apiRequest("/cases");

    if (!cases.cases || cases.cases.length === 0) {
      return;
    }

    const caseId = cases.cases[0].id;

    const docs = await apiRequest(`/cases/${caseId}/documents`);

    if (!docs.documents || docs.documents.length === 0) {
      return;
    }

    const docId = docs.documents[0].id;

    const result = await apiRequest(`/documents/${docId}/compare`);

    const badge = document.querySelector(".modified-badge");

    const panel = document.querySelector(".integrity-panel h4");

    if (result.integrity_status === "MODIFIED") {
      if (badge) {
        badge.textContent = "MODIFIED";
      }

      if (panel) {
        panel.textContent = "Modification Detected";
      }
    } else {
      if (badge) {
        badge.textContent = "UNCHANGED";
      }

      if (panel) {
        panel.textContent = "Integrity Verified";
      }
    }
  } catch (error) {
    console.error("Integrity status failed:", error);
  }
}

/* =========================
   LOAD AUDIT ACTIVITY
========================= */

async function loadAuditActivity() {
  try {
    const cases = await apiRequest("/cases");

    if (!cases.cases || cases.cases.length === 0) {
      return;
    }

    const caseId = cases.cases[0].id;

    const docs = await apiRequest(`/cases/${caseId}/documents`);

    if (!docs.documents || docs.documents.length === 0) {
      return;
    }

    const docId = docs.documents[0].id;

    const result = await apiRequest(`/documents/${docId}/audit`);

    const activityCard = document.querySelector(".activity-card");

    if (!activityCard) {
      return;
    }

    if (!result.audit_trail || result.audit_trail.length === 0) {
      activityCard.innerHTML = `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div>
                        <strong>No audit activity yet</strong>
                        <p>No document actions have been recorded.</p>
                    </div>
                </div>
            `;

      return;
    }

    activityCard.innerHTML = result.audit_trail
      .slice(0, 5)
      .map((log) => {
        const date = new Date(log.timestamp);

        const formattedDate = date.toLocaleDateString("en-IN", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        });

        const formattedTime = date.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
        });

        return `
                        <div class="timeline-item">

                            <div class="timeline-dot"></div>

                            <div>

                                <strong>
                                    ${log.action}
                                </strong>

                                <p>
                                    ${log.details || "Document activity recorded."}
                                </p>

                                <span>
                                    ${log.performed_by}
                                    · ${formattedDate}
                                    · ${formattedTime}
                                </span>

                            </div>

                        </div>
                    `;
      })
      .join("");
  } catch (error) {
    console.error("Audit activity failed:", error);
  }
}

/* =========================
   UPDATE DOCUMENT CARD
========================= */

function updateDocumentCard(data) {
  const name = document.querySelector(".document-main strong");

  const info = document.querySelector(".document-main span");

  const hash = document.querySelector(".document-hash code");

  if (name) {
    name.textContent = data.filename;
  }

  if (info) {
    info.textContent = `${data.document_type} · Version ${data.version}`;
  }

  if (hash) {
    hash.textContent = data.sha256.substring(0, 16) + "...";
  }
}

/* =========================
   REPORT
========================= */

function setupReportButton() {
  const button = document.querySelector(".view-btn");

  if (!button) {
    return;
  }

  button.onclick = showIntegrityReport;
}

function showIntegrityReport() {
  document.body.innerHTML = `

        <div style="
            min-height:100vh;
            background:#f5f7fb;
            font-family:Arial,sans-serif;
            color:#172033;
        ">

            <div style="
                height:75px;
                background:#101827;
                color:white;
                display:flex;
                align-items:center;
                justify-content:space-between;
                padding:0 40px;
            ">

                <button
                    onclick="location.reload()"
                    style="
                        background:none;
                        border:0;
                        color:#b8c2d3;
                        cursor:pointer;
                        font-size:14px;
                    "
                >
                    ← Back to Dashboard
                </button>

                <strong style="
                    letter-spacing:2px;
                    font-size:17px;
                ">
                    NEXORA
                </strong>

                <span style="
                    color:#8996aa;
                    font-size:10px;
                    letter-spacing:1px;
                ">
                    DOCUMENT INTEGRITY REPORT
                </span>

            </div>


            <div style="
                max-width:1100px;
                margin:auto;
                padding:40px 25px;
            ">

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    margin-bottom:25px;
                ">

                    <div>

                        <div style="
                            color:#8190a8;
                            font-size:10px;
                            font-weight:bold;
                            letter-spacing:1.5px;
                            margin-bottom:8px;
                        ">
                            SECURITY ANALYSIS
                        </div>

                        <h1 style="
                            margin:0;
                            font-size:30px;
                        ">
                            Document Integrity Report
                        </h1>

                        <p style="
                            color:#718096;
                            font-size:13px;
                        ">
                            Cryptographic and version verification
                        </p>

                    </div>


                    <div style="
                        background:#fff0f0;
                        color:#c23e3e;
                        border:1px solid #ffd0d0;
                        padding:12px 18px;
                        border-radius:9px;
                        font-weight:bold;
                        font-size:12px;
                    ">
                        ⚠ MODIFICATION DETECTED
                    </div>

                </div>


                <div style="
                    background:white;
                    border:1px solid #e5e9f0;
                    border-radius:13px;
                    padding:24px;
                    margin-bottom:22px;
                ">

                    <small style="
                        color:#8190a8;
                        font-weight:bold;
                    ">
                        DOCUMENT
                    </small>

                    <h3>
                        Nexora_Sample_FIR_NXR-2026-001.pdf
                    </h3>

                    <span style="
                        color:#718096;
                        font-size:12px;
                    ">
                        First Information Report ·
                        Case NXR-2026-001
                    </span>

                </div>


                <h3>
                    Cryptographic Fingerprint
                </h3>


                <div style="
                    display:grid;
                    grid-template-columns:1fr 1fr;
                    gap:15px;
                    margin-bottom:25px;
                ">

                    <div style="
                        background:white;
                        border:1px solid #e5e9f0;
                        border-radius:12px;
                        padding:20px;
                    ">

                        <small>
                            ORIGINAL — VERSION 1
                        </small>

                        <p style="
                            font-family:monospace;
                            font-size:10px;
                            word-break:break-all;
                        ">
                            c8f3653d0e0ecb9fc2a4c5f8c87b78971ce8e67945e8071381fd6b5dd3bee66d
                        </p>

                    </div>


                    <div style="
                        background:#fffafa;
                        border:1px solid #ffd2d2;
                        border-radius:12px;
                        padding:20px;
                    ">

                        <small>
                            CURRENT — VERSION 2
                        </small>

                        <p style="
                            font-family:monospace;
                            font-size:10px;
                            word-break:break-all;
                        ">
                            9f7c0a42663fb6661f0c2479530e80664793b5661c877496ce3c49bc447dcfad
                        </p>

                    </div>

                </div>


                <div style="
                    background:#fff1f1;
                    border:1px solid #ffd0d0;
                    border-radius:13px;
                    padding:25px;
                    margin-bottom:25px;
                ">

                    <small>
                        DETECTED CHANGE
                    </small>

                    <h2 style="
                        color:#bd3e3e;
                    ">
                        Incident Date Modified
                    </h2>

                    <div style="
                        display:flex;
                        gap:30px;
                        align-items:center;
                    ">

                        <strong>
                            26 September 2026
                        </strong>

                        <span style="
                            font-size:24px;
                            color:#c94b4b;
                        ">
                            →
                        </span>

                        <strong>
                            27 September 2026
                        </strong>

                    </div>

                </div>


                <div style="
                    background:white;
                    border:1px solid #e5e9f0;
                    border-radius:13px;
                    padding:25px;
                ">

                    <small>
                        CHAIN OF CUSTODY
                    </small>

                    <h2>
                        Audit Trail
                    </h2>

                    <div style="
                        background:#f7f9fc;
                        padding:18px;
                        border-radius:9px;
                        margin-top:15px;
                    ">

                        <strong>
                            ● INTEGRITY_CHECK
                        </strong>

                        <p style="
                            color:#718096;
                            font-size:12px;
                        ">
                            Compared Version 1 with Version 2.
                            Integrity status: MODIFIED.
                            Changes detected: 2.
                        </p>

                        <small>
                            Performed by Harsh ·
                            28 Sep 2026 · 18:32
                        </small>

                    </div>

                </div>

            </div>

        </div>
    `;
}
function setupUpload() {
  const uploadButton = document.querySelector(".primary-btn");

  if (!uploadButton) {
    console.error("Upload button not found.");
    return;
  }

  uploadButton.onclick = () => {
    const input = document.createElement("input");

    input.type = "file";
    input.accept = ".pdf";

    input.onchange = async (event) => {
      const file = event.target.files[0];

      if (!file) {
        return;
      }

      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("Please select a PDF file.");
        return;
      }

      if (!token) {
        alert("Please login first.");
        return;
      }

      const formData = new FormData();

      formData.append("file", file);

      try {
        uploadButton.textContent = "Uploading...";

        uploadButton.disabled = true;

        const result = await apiRequest("/cases/1/documents", {
          method: "POST",
          body: formData,
        });

        alert(
          "Document uploaded successfully!\n\n" +
            "Document: " +
            result.filename +
            "\n\nSHA-256:\n" +
            result.sha256,
        );

        updateDocumentCard(result);
      } catch (error) {
        alert("Upload failed:\n" + error.message);

        console.error("Upload failed:", error);
      } finally {
        uploadButton.textContent = "+ Upload Document";

        uploadButton.disabled = false;
      }
    };

    input.click();
  };
}
