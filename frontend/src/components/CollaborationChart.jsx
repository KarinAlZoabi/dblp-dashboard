import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";

function CollaborationChart({ data }) {
  return (
    <div className="chart-card">

      <h2>Author Collaboration Over Time</h2>

      <p>
        Growth of multi-author research and average authors per publication
      </p>

      <ResponsiveContainer width="100%" height={450}>

        <LineChart data={data}>

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
  );
}

export default CollaborationChart;