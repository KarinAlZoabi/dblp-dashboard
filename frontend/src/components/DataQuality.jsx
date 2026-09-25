function getQualityClass(value) {
  if (value < 5) return "quality-good";
  if (value < 25) return "quality-warning";
  return "quality-bad";
}

function DataQuality({ data }) {
  return (
    <div className="chart-card">

      <h2>Metadata Completeness</h2>

      <p className="chart-subtitle">
        Percentage of records missing author, title, or year information
      </p>

      <div className="quality-table">

        <div className="quality-row quality-header">
          <div>Publication Type</div>
          <div>Author</div>
          <div>Title</div>
          <div>Year</div>
        </div>

        {Object.entries(data).map(([type, values]) => (
          <div className="quality-row" key={type}>

            <div className="quality-type">
              {type}
            </div>

            <div
              className={`quality-cell ${getQualityClass(
                values.missing_author_pct
              )}`}
            >
              {values.missing_author_pct.toFixed(2)}%
            </div>

            <div
              className={`quality-cell ${getQualityClass(
                values.missing_title_pct
              )}`}
            >
              {values.missing_title_pct.toFixed(2)}%
            </div>

            <div
              className={`quality-cell ${getQualityClass(
                values.missing_year_pct
              )}`}
            >
              {values.missing_year_pct.toFixed(2)}%
            </div>

          </div>
        ))}

      </div>

      <div className="quality-legend">

        <span>
          <span className="legend-dot good"></span>
          Low missing data
        </span>

        <span>
          <span className="legend-dot warning"></span>
          Moderate
        </span>

        <span>
          <span className="legend-dot bad"></span>
          High missing data
        </span>

      </div>

    </div>
  );
}

export default DataQuality;