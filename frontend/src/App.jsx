import { useEffect, useState } from "react";
import axios from "axios";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend
} from "recharts";

import "./App.css";


function App() {
  const [kpis, setKpis] = useState(null);
  const [yearlyData, setYearlyData] = useState([]);
const [publicationTypes, setPublicationTypes] = useState([]);
const [publicationTypesByYear, setPublicationTypesByYear] = useState([]);
const [collaboration, setCollaboration] = useState([]);
const [venues, setVenues] = useState({
  journals: [],
  conferences: []
});
const [dataQuality, setDataQuality] = useState({});

  useEffect(() => {
    // Get KPI data
    axios
      .get("http://127.0.0.1:8000/api/kpis")
      .then((response) => {
        setKpis(response.data);
      })
      .catch((error) => {
        console.error("Error fetching KPIs:", error);
      });

    // Get yearly publication data
    axios
      .get("http://127.0.0.1:8000/api/publications/yearly")
      .then((response) => {
        console.log("Yearly data:", response.data);

        // Convert API response into chart-friendly format
        const data = Object.entries(response.data).map(
          ([year, publications]) => ({
            year: Number(year),
            publications,
          })
        );

        setYearlyData(data);
      })
      .catch((error) => {
        console.error("Error fetching yearly publications:", error);
      });

      axios
  .get("http://127.0.0.1:8000/api/publications/types")
  .then((response) => {
    const data = Object.entries(response.data).map(([type, count]) => ({
      type,
      count
    }));

    setPublicationTypes(data);
  })
  .catch((error) => {
    console.error("Error fetching publication types:", error);
  });

  axios
  .get("http://127.0.0.1:8000/api/publications/types-by-year")
  .then((response) => {
    console.log("Yearly type data:", response.data);

    const data = Object.entries(response.data).map(([year, types]) => ({
      year: Number(year),
      article: types.article || 0,
      inproceedings: types.inproceedings || 0,
      phdthesis: types.phdthesis || 0,
      incollection: types.incollection || 0,
      proceedings: types.proceedings || 0,
      book: types.book || 0,
      mastersthesis: types.mastersthesis || 0
    }));

    console.log("Chart data:", data);

    setPublicationTypesByYear(data);
  })
  .catch((error) => {
    console.error(
      "Error fetching publication types by year:",
      error
    );
  });

  axios
  .get("http://127.0.0.1:8000/api/collaboration")
  .then((response) => {
    const data = Object.entries(response.data).map(([year, values]) => ({
      year: Number(year),
      multi_author_pct: values.multi_author_pct,
      avg_authors: values.avg_authors
    }));

    setCollaboration(data);
  })
  .catch((error) => {
    console.error("Error fetching collaboration data:", error);
  });

  axios
  .get("http://127.0.0.1:8000/api/venues")
  .then((response) => {
    setVenues(response.data);
  })
  .catch((error) => {
    console.error("Error fetching venues:", error);
  });

  axios
  .get("http://127.0.0.1:8000/api/data-quality")
  .then((response) => {
    setDataQuality(response.data);
  })
  .catch((error) => {
    console.error("Error fetching data quality:", error);
  });
  }, []);


  if (!kpis) {
    return <p>Loading...</p>;
  }
const getQualityClass = (value) => {
  if (value === 0) return "quality-good";
  if (value < 5) return "quality-good";
  if (value < 25) return "quality-warning";
  return "quality-bad";
};

  return (
    <div className="dashboard">

      {/* HEADER */}

      <header className="dashboard-header">
        <h1>DBLP Dashboard</h1>
        <p>
          Publication trends and research collaboration analysis
        </p>
      </header>


      {/* KPI CARDS */}

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


      {/* PUBLICATIONS OVER TIME */}

      <section className="chart-card">

        <div className="chart-header">
          <div>
            <h2>Publications Over Time</h2>

            <p>
              Number of publications recorded by year
            </p>
          </div>
        </div>


        <div className="chart-container">

          <ResponsiveContainer width="100%" height={400}>

            <LineChart data={yearlyData}>

              <CartesianGrid strokeDasharray="3 3" />

              <XAxis
                dataKey="year"
                tick={{ fontSize: 12 }}
              />

              <YAxis
                tick={{ fontSize: 12 }}
                tickFormatter={(value) =>
                  value.toLocaleString()
                }
              />

              <Tooltip
                formatter={(value) =>
                  value.toLocaleString()
                }
                labelFormatter={(year) =>
                  `Year: ${year}`
                }
              />

              <Line
                type="monotone"
                dataKey="publications"
                stroke="#6366f1"
                strokeWidth={3}
                dot={false}
              />

            </LineChart>

          </ResponsiveContainer>

        </div>

      </section>

{/* PUBLICATION TYPES */}
      <div className="chart-card">
  <h2>Publication Types</h2>
  <p>Distribution of publications by type</p>

  <ResponsiveContainer width="100%" height={400}>
    <BarChart data={publicationTypes}>
      <CartesianGrid strokeDasharray="3 3" />

      <XAxis
        dataKey="type"
        angle={-20}
        textAnchor="end"
        height={80}
      />

      <YAxis />

      <Tooltip />

      <Bar
        dataKey="count"
        fill="#6366f1"
      />
    </BarChart>
  </ResponsiveContainer>
</div>

{/* Publications over time */}

<div className="chart-card">
  <h2>Publication Types Over Time</h2>

  <p>
    How different publication types have changed over the years
  </p>

  <ResponsiveContainer width="100%" height={450}>
    <BarChart data={publicationTypesByYear}>

      <CartesianGrid strokeDasharray="3 3" />

      <XAxis
        dataKey="year"
      />

      <YAxis />

      <Tooltip />

      <Bar
        dataKey="article"
        stackId="types"
      />

      <Bar
        dataKey="inproceedings"
        stackId="types"
      />

      <Bar
        dataKey="phdthesis"
        stackId="types"
      />

      <Bar
        dataKey="incollection"
        stackId="types"
      />

      <Bar
        dataKey="proceedings"
        stackId="types"
      />

      <Bar
        dataKey="book"
        stackId="types"
      />

      <Bar
        dataKey="mastersthesis"
        stackId="types"
      />

    </BarChart>
  </ResponsiveContainer>
</div>

{/* Author collaboration */}

<div className="chart-card">
  <h2>Author Collaboration Over Time</h2>

  <p>
    Growth of multi-author research and average authors per publication
  </p>

  <ResponsiveContainer width="100%" height={450}>
    <LineChart data={collaboration}>

      <CartesianGrid strokeDasharray="3 3" />

      <XAxis dataKey="year" />

      <YAxis
        yAxisId="left"
        domain={[0, 100]}
        tickFormatter={(value) => `${value}%`}
      />

      <YAxis
        yAxisId="right"
        orientation="right"
      />

      <Tooltip />

      <Legend />

      <Line
        yAxisId="left"
        type="monotone"
        dataKey="multi_author_pct"
        name="Multi-author %"
        dot={false}
      />

      <Line
        yAxisId="right"
        type="monotone"
        dataKey="avg_authors"
        name="Average Authors"
        dot={false}
      />

    </LineChart>
  </ResponsiveContainer>
</div>

<div className="chart-card">
  <h2>Top Journals</h2>

  <p>Most common publication venues in the dataset</p>

  <ResponsiveContainer width="100%" height={500}>
    <BarChart
      data={venues.journals.slice(0, 10)}
      layout="vertical"
      margin={{ left: 40, right: 30 }}
    >
      <CartesianGrid strokeDasharray="3 3" />

      <XAxis type="number" />

      <YAxis
        type="category"
        dataKey="venue"
        width={180}
      />

      <Tooltip />

      <Bar
        dataKey="count"
      />
    </BarChart>
  </ResponsiveContainer>
</div>

<div className="chart-card">
  <h2>Top Conferences</h2>

  <p>Most common conference publication venues in the dataset</p>

  <ResponsiveContainer width="100%" height={500}>
    <BarChart
      data={venues.conferences.slice(0, 10)}
      layout="vertical"
      margin={{ left: 40, right: 30 }}
    >
      <CartesianGrid strokeDasharray="3 3" />

      <XAxis type="number" />

      <YAxis
        type="category"
        dataKey="venue"
        width={140}
      />

      <Tooltip />

      <Bar dataKey="count" />
    </BarChart>
  </ResponsiveContainer>
</div>

<div className="chart-card">
  <h2>Data Quality</h2>

  <p>
    Percentage of publications with missing metadata
  </p>

 {/* ============================================================
    DATA QUALITY / METADATA COMPLETENESS
============================================================ */}

<div className="chart-card">
  <h2>Metadata Completeness</h2>
  <p className="chart-subtitle">
    Percentage of records missing author, title, or year information
  </p>

  <div className="quality-table">

    {/* Header */}
    <div className="quality-row quality-header">
      <div>Publication Type</div>
      <div>Author</div>
      <div>Title</div>
      <div>Year</div>
    </div>

    {Object.entries(dataQuality).map(([type, values]) => (
      <div className="quality-row" key={type}>

        <div className="quality-type">
          {type}
        </div>

       <div className={`quality-cell ${getQualityClass(values.missing_author_pct)}`}>
  {values.missing_author_pct.toFixed(2)}%
</div>

<div className={`quality-cell ${getQualityClass(values.missing_title_pct)}`}>
  {values.missing_title_pct.toFixed(2)}%
</div>

<div className={`quality-cell ${getQualityClass(values.missing_year_pct)}`}>
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
</div>
      {/* COLLABORATION SUMMARY */}

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

    </div>
  );
}

export default App;