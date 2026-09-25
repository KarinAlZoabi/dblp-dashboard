import { useEffect, useState } from "react";

import {
  getKpis,
  getYearlyPublications,
  getPublicationTypes,
  getPublicationTypesByYear,
  getCollaboration,
  getVenues,
  getDataQuality,
  getTopicsOverTime
} from "./api/api";

import Header from "./components/Header";
import KpiCards from "./components/KpiCards";
import PublicationsChart from "./components/PublicationsChart";
import PublicationTypesChart from "./components/PublicationTypesChart";
import TypesOverTimeChart from "./components/TypesOverTimeChart";
import CollaborationChart from "./components/CollaborationChart";
import VenuesCharts from "./components/VenuesCharts";
import DataQuality from "./components/DataQuality";
import SummaryCards from "./components/SummaryCards";
import TopicRiverChart from "./components/TopicRiverChart";

import "./App.css";

function App() {
  const [kpis, setKpis] = useState(null);

  // Original unfiltered data
  const [yearlyData, setYearlyData] = useState([]);
  const [publicationTypes, setPublicationTypes] = useState([]);
  const [publicationTypesByYear, setPublicationTypesByYear] = useState([]);
  const [collaboration, setCollaboration] = useState([]);
  const [venues, setVenues] = useState({
    journals: [],
    conferences: []
  });
  const [dataQuality, setDataQuality] = useState({});
  const [topicsOverTime, setTopicsOverTime] = useState([]);

  // Filters
  const [startYear, setStartYear] = useState(1936);
  const [endYear, setEndYear] = useState(2027);
  const [selectedType, setSelectedType] = useState("all");

  useEffect(() => {
    getKpis()
      .then((response) => {
        setKpis(response.data);
      })
      .catch((error) => {
        console.error("Error fetching KPIs:", error);
      });

    getYearlyPublications()
      .then((response) => {
        const data = Object.entries(response.data).map(
          ([year, publications]) => ({
            year: Number(year),
            publications
          })
        );

        setYearlyData(data);
      })
      .catch((error) => {
        console.error("Error fetching yearly publications:", error);
      });

    getPublicationTypes()
      .then((response) => {
        const data = Object.entries(response.data).map(
          ([type, count]) => ({
            type,
            count
          })
        );

        setPublicationTypes(data);
      })
      .catch((error) => {
        console.error("Error fetching publication types:", error);
      });

    getPublicationTypesByYear()
      .then((response) => {
        const data = Object.entries(response.data).map(
          ([year, types]) => ({
            year: Number(year),
            article: types.article || 0,
            inproceedings: types.inproceedings || 0,
            phdthesis: types.phdthesis || 0,
            incollection: types.incollection || 0,
            proceedings: types.proceedings || 0,
            book: types.book || 0,
            mastersthesis: types.mastersthesis || 0
          })
        );

        setPublicationTypesByYear(data);
      })
      .catch((error) => {
        console.error(
          "Error fetching publication types by year:",
          error
        );
      });

    getCollaboration()
      .then((response) => {
        const data = Object.entries(response.data).map(
          ([year, values]) => ({
            year: Number(year),
            multi_author_pct: values.multi_author_pct,
            avg_authors: values.avg_authors
          })
        );

        setCollaboration(data);
      })
      .catch((error) => {
        console.error("Error fetching collaboration data:", error);
      });

    getVenues()
      .then((response) => {
        setVenues(response.data);
      })
      .catch((error) => {
        console.error("Error fetching venues:", error);
      });

    getDataQuality()
      .then((response) => {
        setDataQuality(response.data);
      })
      .catch((error) => {
        console.error("Error fetching data quality:", error);
      });

    getTopicsOverTime()
      .then((response) => {
        const data = Object.entries(response.data).map(
          ([year, topics]) => ({
            year: Number(year),
            ...topics
          })
        );

        setTopicsOverTime(data);
      })
      .catch((error) => {
        console.error("Error fetching topic river data:", error);
      });
  }, []);

  // ============================================================
  // FILTERED DATA
  // ============================================================

  const filteredYearlyData = yearlyData.filter(
    (item) =>
      item.year >= startYear &&
      item.year <= endYear
  );

  const filteredTypesByYear = publicationTypesByYear
    .filter(
      (item) =>
        item.year >= startYear &&
        item.year <= endYear
    )
    .map((item) => {
      if (selectedType === "all") {
        return item;
      }

      return {
        year: item.year,
        [selectedType]: item[selectedType] || 0
      };
    });

  const filteredCollaboration = collaboration.filter(
    (item) =>
      item.year >= startYear &&
      item.year <= endYear
  );

  const filteredTopicsOverTime = topicsOverTime.filter(
    (item) =>
      item.year >= startYear &&
      item.year <= endYear
  );

  // ============================================================
  // FILTER VENUES
  // ============================================================

  // Venue data currently contains overall totals, so we do not
  // apply the year/type filter to it yet.
  const filteredVenues = venues;

  // ============================================================
  // RESET FILTERS
  // ============================================================

  const resetFilters = () => {
    setStartYear(1936);
    setEndYear(2027);
    setSelectedType("all");
  };

  if (!kpis) {
    return <p>Loading...</p>;
  }

  return (
    <div className="dashboard">

      {/* HEADER */}

      <Header />


      {/* FILTERS */}

      <section className="filter-card">

        <div className="filter-header">
          <div>
            <h2>Dashboard Filters</h2>

            <p>
              Filter the visualizations by publication year and type.
            </p>
          </div>

          <button
            className="reset-button"
            onClick={resetFilters}
          >
            Reset Filters
          </button>
        </div>


        <div className="filters">

          {/* START YEAR */}

          <div className="filter-group">

            <label htmlFor="start-year">
              From Year
            </label>

            <select
              id="start-year"
              value={startYear}
              onChange={(e) =>
                setStartYear(Number(e.target.value))
              }
            >
              {yearlyData.map((item) => (
                <option
                  key={item.year}
                  value={item.year}
                  disabled={item.year > endYear}
                >
                  {item.year}
                </option>
              ))}
            </select>

          </div>


          {/* END YEAR */}

          <div className="filter-group">

            <label htmlFor="end-year">
              To Year
            </label>

            <select
              id="end-year"
              value={endYear}
              onChange={(e) =>
                setEndYear(Number(e.target.value))
              }
            >
              {yearlyData.map((item) => (
                <option
                  key={item.year}
                  value={item.year}
                  disabled={item.year < startYear}
                >
                  {item.year}
                </option>
              ))}
            </select>

          </div>


          {/* PUBLICATION TYPE */}

          <div className="filter-group">

            <label htmlFor="publication-type">
              Publication Type
            </label>

            <select
              id="publication-type"
              value={selectedType}
              onChange={(e) =>
                setSelectedType(e.target.value)
              }
            >
              <option value="all">
                All Types
              </option>

              <option value="article">
                Article
              </option>

              <option value="inproceedings">
                Inproceedings
              </option>

              <option value="phdthesis">
                PhD Thesis
              </option>

              <option value="incollection">
                Incollection
              </option>

              <option value="proceedings">
                Proceedings
              </option>

              <option value="book">
                Book
              </option>

              <option value="mastersthesis">
                Master's Thesis
              </option>

            </select>

          </div>

        </div>

      </section>


      {/* KPI CARDS */}

      <KpiCards kpis={kpis} />


      {/* CHART GRID */}

      <div className="charts-grid">

        <PublicationsChart
          data={filteredYearlyData}
        />

        <PublicationTypesChart
          data={publicationTypes}
        />

        <TypesOverTimeChart
          data={filteredTypesByYear}
          selectedType={selectedType}
        />

        <CollaborationChart
          data={filteredCollaboration}
        />

        <VenuesCharts
          venues={filteredVenues}
        />

      </div>


      {/* TOPIC RIVER */}

      <div className="full-width-chart">

        <TopicRiverChart
          data={filteredTopicsOverTime}
        />

      </div>


      {/* DATA QUALITY */}

      <div className="full-width-chart">

        <DataQuality
          data={dataQuality}
        />

      </div>


      {/* SUMMARY */}

      <SummaryCards
        kpis={kpis}
      />

    </div>
  );
}

export default App;