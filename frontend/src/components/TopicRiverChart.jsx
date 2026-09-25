import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";

// Distinct palette, cycled if there are more topics than colors
const RIVER_COLORS = [
  "#6366f1", "#ec4899", "#10b981", "#f59e0b", "#3b82f6",
  "#8b5cf6", "#ef4444", "#14b8a6", "#f97316", "#a855f7",
  "#22c55e", "#eab308", "#0ea5e9", "#d946ef", "#84cc16",
  "#f43f5e", "#06b6d4", "#c026d3", "#65a30d", "#e11d48"
];

function TopicRiverChart({ data }) {

  if (!data || data.length === 0) {
    return null;
  }

  // Topic names come straight from the data keys (everything but
  // "year"), so this adapts automatically to whatever vocabulary the
  // topics_over_time.json export used.
  const topics = Object.keys(data[0]).filter(
    (key) => key !== "year"
  );

  return (
    <div className="chart-card">

      <h2>The Topic River</h2>

      <p className="chart-subtitle">
        How research terms extracted from publication titles rise,
        fall, and drift over time
      </p>

      <ResponsiveContainer width="100%" height={480}>

        <AreaChart
          data={data}
          stackOffset="wiggle"
        >

          <XAxis dataKey="year" />

          <YAxis hide />

          <Tooltip
            labelFormatter={(year) => `Year: ${year}`}
          />

          <Legend
            wrapperStyle={{ fontSize: 12 }}
          />

          {topics.map((topic, index) => (
            <Area
              key={topic}
              type="monotone"
              dataKey={topic}
              name={topic}
              stackId="river"
              stroke={RIVER_COLORS[index % RIVER_COLORS.length]}
              fill={RIVER_COLORS[index % RIVER_COLORS.length]}
              fillOpacity={0.85}
              connectNulls
            />
          ))}

        </AreaChart>

      </ResponsiveContainer>

    </div>
  );
}

export default TopicRiverChart;
