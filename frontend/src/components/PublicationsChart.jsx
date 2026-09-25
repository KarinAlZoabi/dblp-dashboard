import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";

function PublicationsChart({ data }) {
  return (
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

          <LineChart data={data}>

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
  );
}

export default PublicationsChart;