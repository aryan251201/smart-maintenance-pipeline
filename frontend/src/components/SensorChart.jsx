import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { useMemo } from "react";

const COLORS = {
  temperature: "#f97316",
  humidity: "#3b82f6",
  pressure: "#10b981",
};

function SensorChart({ data }) {
  const chartData = useMemo(() => {
    const grouped = {};
    for (const row of data) {
      const time = new Date(row.time).toLocaleTimeString();
      if (!grouped[time]) grouped[time] = { time };
      grouped[time][row.metric] = row.value;
      if (row.failure) grouped[time].failure = true;
    }
    return Object.values(grouped).reverse();
  }, [data]);

  if (chartData.length === 0) {
    return <p className="text-gray-400">No sensor data available.</p>;
  }

  const metrics = [...new Set(data.map((d) => d.metric))];

  return (
    <div className="space-y-6">
      {metrics.map((metric) => (
        <div key={metric} className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-2 capitalize">{metric}</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="time"
                stroke="#9ca3af"
                fontSize={11}
                tick={{ fill: "#9ca3af" }}
                interval="preserveStartEnd"
              />
              <YAxis stroke="#9ca3af" fontSize={11} tick={{ fill: "#9ca3af" }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Line
                type="monotone"
                dataKey={metric}
                stroke={COLORS[metric] || "#8b5cf6"}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}

export default SensorChart;
