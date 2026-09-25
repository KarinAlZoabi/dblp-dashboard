import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";

function TypesOverTimeChart({ data, selectedType }) {

  const types = [
    "article",
    "inproceedings",
    "phdthesis",
    "incollection",
    "proceedings",
    "book",
    "mastersthesis"
  ];

  return (
    <div className="chart-card">

      <h2>Publication Types Over Time</h2>

      <p>
        How different publication types have changed over the years
      </p>

      <ResponsiveContainer width="100%" height={450}>

        <BarChart data={data}>

          <CartesianGrid strokeDasharray="3 3" />

          <XAxis dataKey="year" />

          <YAxis />

          <Tooltip />

          <Legend />

          {selectedType === "all" ? (
            types.map((type) => (
              <Bar
                key={type}
                dataKey={type}
                stackId="types"
                name={type}
              />
            ))
          ) : (
            <Bar
              dataKey={selectedType}
              name={selectedType}
            />
          )}

        </BarChart>

      </ResponsiveContainer>

    </div>
  );
}

export default TypesOverTimeChart;