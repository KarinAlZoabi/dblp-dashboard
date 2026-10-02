import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import "./AuthorNetwork.css";

const API_BASE = "http://localhost:8000";

const METRICS = [
  ["degree", "Degree Centrality"],
  ["pagerank", "PageRank"],
  ["eigenvector", "Eigenvector Centrality"],
  ["betweenness", "Approx. Betweenness"],
];

function getValue(node, metric) {
  if (!node) return 0;

  if (metric === "degree") return node.degree_centrality || 0;
  if (metric === "pagerank") return node.pagerank || 0;
  if (metric === "eigenvector") return node.eigenvector_centrality || 0;

  return node.approx_betweenness || 0;
}

function formatMetric(value) {
  if (value === null || value === undefined) return "—";

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) return "—";

  return Math.abs(numericValue) >= 0.01
    ? numericValue.toFixed(5)
    : numericValue.toExponential(3);
}

export default function AuthorNetwork() {
  const graphRef = useRef(null);
  const graphContainerRef = useRef(null);
  const hasAutoFitRef = useRef(false);

  const [metric, setMetric] = useState("degree");
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  const [graphSize, setGraphSize] = useState({
    width: 800,
    height: 520,
  });

  useEffect(() => {
    const element = graphContainerRef.current;

    if (!element) return undefined;

    const updateSize = () => {
      const rect = element.getBoundingClientRect();

      setGraphSize({
        width: Math.max(rect.width, 300),
        height: Math.max(rect.height, 420),
      });
    };

    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(element);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    setData(null);
    setSelected(null);
    setError("");

    hasAutoFitRef.current = false;

    fetch(`${API_BASE}/api/network/${metric}`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            `Network request failed (${response.status})`
          );
        }

        return response.json();
      })
      .then((result) => {
        setData(result);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message);
        }
      });

    return () => controller.abort();
  }, [metric]);

  const graphData = useMemo(() => {
    if (!data) {
      return {
        nodes: [],
        links: [],
      };
    }

    return {
      nodes: data.visualization.nodes.map((node) => ({
        ...node,
        id: node.author_id,
      })),

      links: data.visualization.links.map((link) => ({
        ...link,
      })),
    };
  }, [data]);

  const maxValue = useMemo(() => {
    if (!graphData.nodes.length) return 1;

    return Math.max(
      ...graphData.nodes.map((node) =>
        getValue(node, metric)
      ),
      1e-15
    );
  }, [graphData, metric]);

  const nodeSize = (node) => {
    const value = getValue(node, metric);

    const normalized = Math.sqrt(
      Math.max(value, 0) / maxValue
    );

    return 3.5 + normalized * 7.5;
  };

  const nodeLabel = (node) => `
${node.name}
Publications: ${node.publication_count.toLocaleString()}
Collaborators: ${node.degree.toLocaleString()}
Weighted degree: ${node.weighted_degree.toLocaleString()}
${data?.metric_label}: ${formatMetric(getValue(node, metric))}
  `;

  const resetGraphView = () => {
    setSelected(null);

    if (!graphRef.current) return;

    graphRef.current.zoomToFit(500, 55);
  };

  const handleNodeClick = (node) => {
    setSelected(node);

    if (!graphRef.current) return;

    graphRef.current.centerAt(
      node.x,
      node.y,
      500
    );

    graphRef.current.zoom(
      2.1,
      500
    );
  };

  const handleEngineStop = () => {
    if (
      hasAutoFitRef.current ||
      !graphRef.current
    ) {
      return;
    }

    hasAutoFitRef.current = true;

    graphRef.current.zoomToFit(
      500,
      55
    );
  };

  if (error) {
    return (
      <section className="author-network-section">
        <div className="network-error">
          {error}
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="author-network-section">
        <div className="network-loading">
          Loading co-authorship network…
        </div>
      </section>
    );
  }

  return (
    <section className="author-network-section">
      <div className="network-heading">
        <div>
          <h2>DBLP Co-authorship Network</h2>

          <p>
            Centrality measures were calculated on the full{" "}
            {data.full_network.nodes.toLocaleString()}
            -author network. The visualization shows a focused
            subset of the highest-ranked authors.
          </p>
        </div>

        <label className="metric-control">
          <span>Centrality measure</span>

          <select
            value={metric}
            onChange={(event) =>
              setMetric(event.target.value)
            }
          >
            {METRICS.map(([key, label]) => (
              <option
                key={key}
                value={key}
              >
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="network-summary-row">
        <div className="network-mini-stat">
          <span>Full authors</span>
          <strong>
            {data.full_network.nodes.toLocaleString()}
          </strong>
        </div>

        <div className="network-mini-stat">
          <span>Full edges</span>
          <strong>
            {data.full_network.edges.toLocaleString()}
          </strong>
        </div>

        <div className="network-mini-stat">
          <span>Displayed authors</span>
          <strong>
            {data.visualization.nodes.length.toLocaleString()}
          </strong>
        </div>

        <div className="network-mini-stat">
          <span>Displayed edges</span>
          <strong>
            {data.visualization.links.length.toLocaleString()}
          </strong>
        </div>
      </div>

      <div className="network-layout">
        <div className="network-card graph-card">
          <div className="network-card-title">
            <div>
              <h3>Co-authorship structure</h3>

              <p>
                Node size represents{" "}
                {data.metric_label}. Edge thickness represents
                repeated collaboration.
              </p>
            </div>

            <button
              type="button"
              className="network-reset-button"
              onClick={resetGraphView}
            >
              Reset view
            </button>
          </div>

          <div
            ref={graphContainerRef}
            className="force-graph-wrap"
          >
            <ForceGraph2D
              ref={graphRef}
              width={graphSize.width}
              height={graphSize.height}
              graphData={graphData}
              backgroundColor="#ffffff"
              nodeLabel={nodeLabel}
              nodeVal={nodeSize}
              nodeRelSize={1}
              nodeColor={(node) =>
                selected?.id === node.id
                  ? "#111827"
                  : "#ec4899"
              }
              linkColor={() =>
                "rgba(148, 163, 184, 0.20)"
              }
              linkWidth={(link) =>
                Math.min(
                  0.55 +
                    Math.log1p(
                      link.weight || 1
                    ) *
                      0.55,
                  3
                )
              }
              warmupTicks={60}
              cooldownTicks={75}
              d3AlphaDecay={0.06}
              d3VelocityDecay={0.42}
              enableNodeDrag={true}
              enablePanInteraction={true}
              enableZoomInteraction={true}
              onNodeClick={handleNodeClick}
              onEngineStop={handleEngineStop}
            />
          </div>

          {selected && (
            <div className="author-detail-panel">
              <div className="author-detail-heading">
                <span className="detail-label">
                  Selected author
                </span>

                <h4>{selected.name}</h4>
              </div>

              <div className="author-detail-grid">
                <div>
                  <span>Publications</span>
                  <strong>
                    {selected.publication_count.toLocaleString()}
                  </strong>
                </div>

                <div>
                  <span>Collaborators</span>
                  <strong>
                    {selected.degree.toLocaleString()}
                  </strong>
                </div>

                <div>
                  <span>Weighted degree</span>
                  <strong>
                    {selected.weighted_degree.toLocaleString()}
                  </strong>
                </div>

                <div>
                  <span>
                    {data.metric_label}
                  </span>
                  <strong>
                    {formatMetric(
                      getValue(
                        selected,
                        metric
                      )
                    )}
                  </strong>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="network-card ranking-card">
          <div className="network-card-title">
            <div>
              <h3>
                Top authors by{" "}
                {data.metric_label}
              </h3>

              <p>
                Ranking calculated from the complete
                DBLP co-authorship graph.
              </p>
            </div>
          </div>

          <div className="ranking-chart">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <BarChart
                data={[
                  ...data.ranking,
                ].reverse()}
                layout="vertical"
                margin={{
                  top: 8,
                  right: 18,
                  left: 8,
                  bottom: 8,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                  stroke="#eef2f7"
                />

                <XAxis
                  type="number"
                  tick={{
                    fontSize: 10,
                    fill: "#94a3b8",
                  }}
                  tickFormatter={(value) =>
                    Number(
                      value
                    ).toExponential(1)
                  }
                />

                <YAxis
                  type="category"
                  dataKey="name"
                  width={118}
                  tick={{
                    fontSize: 10,
                    fill: "#64748b",
                  }}
                />

                <Tooltip
                  formatter={(value) => [
                    formatMetric(value),
                    data.metric_label,
                  ]}
                />

                <Bar
                  dataKey="value"
                  fill="#ec4899"
                  radius={[0, 6, 6, 0]}
                  maxBarSize={24}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {metric === "betweenness" && (
            <p className="network-note">
              Approximate betweenness was calculated
              using 200 sampled source nodes from the
              full co-authorship network.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
