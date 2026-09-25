import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";

function PublicationTypesChart({ data }) {
  return (
    <div className="chart-card">

      <h2>Publication Types</h2>

      <p>Distribution of publications by type</p>

      <ResponsiveContainer width="100%" height={400}>

        <BarChart data={data}>

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
  );
}

export default PublicationTypesChart;