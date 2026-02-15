document.querySelectorAll(".report").forEach(report => {
  report.addEventListener("click", async () => {
    if (report.classList.contains("exported")) return;

    const cell = report.closest("td");
    const originalText = report.innerText;

    report.innerText = "Exporting…";

    try {
      const response = await fetch("/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: report.dataset.url,
          report_name: report.dataset.reportName,
          filing_date: report.dataset.filingDate,
          filing_type: report.dataset.filingType,
          ticker: report.dataset.ticker
        })
      });

      const result = await response.json();

      if (result.status === "ok") {
        // Trigger download
        const downloadUrl = `${result.download_url}?filename=${encodeURIComponent(result.filename)}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = result.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Mark as exported
        report.classList.add("exported");
        report.innerText = "✓ " + report.dataset.reportName;
        cell.classList.add("exported");
      } else {
        report.innerText = "Error - " + originalText;
        alert("Export failed: " + (result.message || "Unknown error"));
      }
    } catch (error) {
      report.innerText = "Error - " + originalText;
      alert("Export failed: " + error.message);
    }
  });
});

const filters = document.querySelectorAll("#filters input[type=checkbox]");

function applyFilters() {
  const active = Array.from(filters)
    .filter(cb => cb.checked)
    .map(cb => cb.value);

  document.querySelectorAll("th").forEach((th, index) => {
    const form = th.dataset.filingType;
    const td = document.querySelectorAll("td")[index];

    const show = active.includes(form);

    th.style.display = show ? "" : "none";
    td.style.display = show ? "" : "none";
  });
}

filters.forEach(cb => cb.addEventListener("change", applyFilters));
