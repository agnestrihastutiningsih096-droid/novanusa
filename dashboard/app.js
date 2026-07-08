const pages = {
  home: {
    title: "Home",
    subtitle: "Enterprise Procurement Intelligence Overview",
    html: `
      <div class="grid kpi">
        <div class="card kpi-card"><span>Institutions</span><div class="value">4,699</div><p>Matched SiRUP institutions</p></div>
        <div class="card kpi-card"><span>Needs</span><div class="value">23,259</div><p>Detected procurement needs</p></div>
        <div class="card kpi-card"><span>Email Ready</span><div class="value">150</div><p>Ready Mitracom targets</p></div>
        <div class="card kpi-card"><span>Sent</span><div class="value">25</div><p>Pilot outreach sent</p></div>
      </div>

      <div class="grid two section-gap">
        <div class="card">
          <h3>Need Domains</h3>
          <div class="domain-list">
            <span class="badge">IT Hardware</span>
            <span class="badge">Printer / Scanner</span>
            <span class="badge">Networking</span>
            <span class="badge">CCTV</span>
            <span class="badge">Medical Device</span>
            <span class="badge">Laboratory</span>
            <span class="badge">Radiology</span>
            <span class="badge">Dental</span>
          </div>
        </div>

        <div class="card">
          <h3>Business Focus</h3>
          <ul class="clean-list">
            <li><b>Mitracom:</b> validate IT, printer, and networking outreach.</li>
            <li><b>Medical Device:</b> show SiRUP needs and principal gaps.</li>
            <li><b>Dashboard:</b> fix institution → need → opportunity flow.</li>
          </ul>
        </div>
      </div>

      <div class="grid two section-gap">
        <div class="card">
          <h3>Recent Opportunities</h3>
          <table class="table">
            <tr><th>Institution</th><th>Domain</th><th>Status</th></tr>
            <tr><td>Dinas Pendidikan</td><td>IT Hardware</td><td><span class="status ready">Email Ready</span></td></tr>
            <tr><td>RSUD</td><td>Medical Device</td><td><span class="status gap">Principal Gap</span></td></tr>
            <tr><td>Dinas Kesehatan</td><td>Laboratory</td><td><span class="status review">Need Review</span></td></tr>
          </table>
        </div>

        <div class="card">
          <h3>Demo Readiness</h3>
          <div class="timeline">
            <div><b>1</b><span>Open Institution Profile</span></div>
            <div><b>2</b><span>Show original SiRUP needs</span></div>
            <div><b>3</b><span>Show NovaNusa analysis</span></div>
            <div><b>4</b><span>Match principal and product</span></div>
            <div><b>5</b><span>Prepare outreach</span></div>
          </div>
        </div>
      </div>
    `
  },

  opportunities: {
    title: "Opportunities",
    subtitle: "Pipeline peluang NovaNusa",
    html: `
      <div class="pipeline">
        ${["Need Detected","Need Reviewed","Principal Matched","Product Matched","Email Draft","Approved","Sent","Follow Up","Negotiation","Won","Lost"].map(stage => `
          <div class="stage">
            <h3>${stage}</h3>
            <div class="item">Dinas Pendidikan — IT Hardware</div>
            <div class="item">RSUD — Medical Device</div>
          </div>
        `).join("")}
      </div>
    `
  },

  institutions: {
    title: "Institutions",
    subtitle: "Profil instansi, kebutuhan, kontak, dan histori",
    html: `
      <div class="profile">
        <div class="card">
          <h3>Institution Summary</h3>
          <p><b>Nama:</b> Dinas Kesehatan Kabupaten Sleman</p>
          <p><b>KLD:</b> Pemerintah Daerah</p>
          <p><b>Lokasi:</b> DI Yogyakarta</p>
          <p><b>Website:</b> tersedia</p>
          <p><b>Email:</b> perlu validasi</p>
        </div>
        <div class="card">
          <h3>Institution Profile Flow</h3>
          <span class="badge">SiRUP Original Data</span>
          <span class="badge">Need Timeline</span>
          <span class="badge">Need Analysis</span>
          <span class="badge">Matched Principals</span>
          <span class="badge">Matched Products</span>
          <span class="badge">Outreach History</span>
          <span class="badge">Follow Up</span>
          <span class="badge">Knowledge</span>
        </div>
      </div>
      <div class="card section-gap">
        <h3>Sample Institution List</h3>
        <table class="table">
          <tr><th>Institution</th><th>Domain</th><th>Value</th><th>Status</th></tr>
          <tr><td>Dinas Kesehatan</td><td>Medical Device</td><td>High</td><td>Need Detected</td></tr>
          <tr><td>Dinas Pendidikan</td><td>IT Hardware</td><td>High</td><td>Email Ready</td></tr>
          <tr><td>RSUD</td><td>Laboratory</td><td>Medium</td><td>Principal Gap</td></tr>
        </table>
      </div>
    `
  },

  needs: {
    title: "Needs",
    subtitle: "Explorer kebutuhan pemerintah berdasarkan SiRUP",
    html: `
      <div class="card"><h3>Need Domains</h3>
        ${["IT Hardware","Networking","CCTV","Audio Video","Camera","Drone","Office Equipment","Furniture","Medical Device","Laboratory","Radiology","Dental","Education","Construction","Security","Other"].map(x => `<span class="badge">${x}</span>`).join("")}
      </div>
      <div class="card section-gap"><h3>Gap Opportunity</h3><p>Need ditemukan tetapi principal belum tersedia → peluang Business Development.</p></div>
    `
  },

  principals: {
    title: "Principals",
    subtitle: "Business Development principal dan katalog",
    html: `
      <div class="grid two">
        <div class="card"><h3>Mitracom</h3><p>Domain: IT Hardware, Printer, Networking</p><p>Status: Active Outreach</p></div>
        <div class="card"><h3>Medical Device Principal</h3><p>Domain: Medical Device, Laboratory, Radiology</p><p>Status: Prospect</p></div>
      </div>
    `
  },

  products: {
    title: "Products",
    subtitle: "Katalog produk dan matching",
    html: `<div class="card"><h3>Product Catalog</h3><p>Produk terhubung ke Principal, Domain, Institution, Opportunity, dan Outreach.</p></div>`
  },

  outreach: {
    title: "Outreach",
    subtitle: "Email, campaign, dan follow up",
    html: `
      <div class="card">
        <h3>Outreach Status</h3>
        <span class="badge">Draft</span><span class="badge">Review</span><span class="badge">Approved</span><span class="badge">Sent</span><span class="badge">Follow Up</span><span class="badge">Replied</span><span class="badge">Meeting</span>
      </div>
    `
  },

  ai: {
    title: "AI Intelligence",
    subtitle: "Matching, scoring, recommendation, explainability",
    html: `<div class="card"><h3>Explainability</h3><p>Setiap rekomendasi wajib memiliki dasar kebutuhan, sumber data, alasan kecocokan, confidence, risiko, dan next action.</p></div>`
  },

  analytics: {
    title: "Analytics",
    subtitle: "Analitik peluang dan performa",
    html: `<div class="card"><h3>Analytics</h3><p>Opportunity by domain, province, institution type, principal, product category, outreach performance, and gap opportunity.</p></div>`
  },

  knowledge: {
    title: "Knowledge",
    subtitle: "Catatan enterprise dan pembelajaran",
    html: `<div class="card"><h3>Knowledge Base</h3><p>Institution knowledge, principal knowledge, product knowledge, decision history, notes, lessons learned.</p></div>`
  },

  admin: {
    title: "Administration",
    subtitle: "Import, validation, review queue, audit",
    html: `<div class="card"><h3>Administration</h3><p>Data import, validation, contact management, review queue, audit history.</p></div>`
  },

  settings: {
    title: "Settings",
    subtitle: "Pengaturan dashboard",
    html: `<div class="card"><h3>Settings</h3><p>Domain setting, principal setting, product setting, outreach setting, dashboard preference.</p></div>`
  }
};

function render(page) {
  document.querySelectorAll(".nav").forEach(btn => btn.classList.remove("active"));
  document.querySelector(`[data-page="${page}"]`).classList.add("active");
  document.getElementById("page-title").textContent = pages[page].title;
  document.getElementById("page-subtitle").textContent = pages[page].subtitle;
  document.getElementById("content").innerHTML = pages[page].html;
}

document.querySelectorAll(".nav").forEach(btn => {
  btn.addEventListener("click", () => render(btn.dataset.page));
});

render("home");
