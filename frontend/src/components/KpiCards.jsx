function KpiCards({ kpis }) {
  return (
    <section className="kpi-grid">

      <div className="kpi-card">
        <span className="kpi-label">
          Analyzed Publications
        </span>

        <span className="kpi-value">
          {kpis.total_analyzed_publications.toLocaleString()}
        </span>
      </div>

      <div className="kpi-card">
        <span className="kpi-label">
          Average Authors
        </span>

        <span className="kpi-value">
          {kpis.average_authors}
        </span>
      </div>

      <div className="kpi-card">
        <span className="kpi-label">
          Median Authors
        </span>

        <span className="kpi-value">
          {kpis.median_authors}
        </span>
      </div>

      <div className="kpi-card">
        <span className="kpi-label">
          Maximum Authors
        </span>

        <span className="kpi-value">
          {kpis.maximum_authors}
        </span>
      </div>

    </section>
  );
}

export default KpiCards;