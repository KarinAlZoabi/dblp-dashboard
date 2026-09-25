import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";

function VenueChart({ title, subtitle, data }) {
  return (
    <div className="chart-card">

      <h2>{title}</h2>

      <p>{subtitle}</p>

      <ResponsiveContainer width="100%" height={500}>

        <BarChart
          data={data.slice(0, 10)}
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

          <Bar dataKey="count" />

        </BarChart>

      </ResponsiveContainer>

    </div>
  );
}

function VenuesCharts({ venues }) {
  return (
    <>
      <VenueChart
        title="Top Journals"
        subtitle="Most common publication venues in the dataset"
        data={venues.journals}
      />

      <VenueChart
        title="Top Conferences"
        subtitle="Most common conference publication venues in the dataset"
        data={venues.conferences}
      />
    </>
  );
}

export default VenuesCharts;