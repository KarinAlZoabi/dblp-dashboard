function SummaryCards({ kpis }) {
  return (
    <section className="summary-grid">

      <div className="summary-card">
        <span className="summary-label">
          Single-author publications
        </span>

        <strong>
          {kpis.single_author_publications.toLocaleString()}
        </strong>

        <span className="summary-percentage">
          {kpis.single_author_pct}%
        </span>
      </div>

      <div className="summary-card">
        <span className="summary-label">
          Multi-author publications
        </span>

        <strong>
          {kpis.multi_author_publications.toLocaleString()}
        </strong>

        <span className="summary-percentage">
          {kpis.multi_author_pct}%
        </span>
      </div>

      <div className="summary-card">
        <span className="summary-label">
          Duplicate keys
        </span>

        <strong>
          {kpis.duplicate_keys}
        </strong>

        <span className="summary-percentage">
          Data quality check
        </span>
      </div>

    </section>
  );
}

export default SummaryCards;