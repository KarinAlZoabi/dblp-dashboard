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
} from "recharts";

import "./App.css";


function App() {
  const [kpis, setKpis] = useState(null);
  const [yearlyData, setYearlyData] = useState([]);

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
  }, []);


  if (!kpis) {
    return <p>Loading...</p>;
  }


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