import { useState, useEffect } from "react";

function AlertHistory({ apiUrl }) {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  async function fetchAlerts() {
    try {
      const res = await fetch(`${apiUrl}/alerts/recent`);
      if (res.ok) setAlerts(await res.json());
    } catch (err) {
      // API endpoint may not exist yet
    }
  }

  if (alerts.length === 0) {
    return <p className="text-gray-400">No recent alerts.</p>;
  }

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-700">
          <tr>
            <th className="text-left p-3 text-gray-300">Time</th>
            <th className="text-left p-3 text-gray-300">Device</th>
            <th className="text-left p-3 text-gray-300">Probability</th>
            <th className="text-left p-3 text-gray-300">Channel</th>
            <th className="text-left p-3 text-gray-300">Status</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert, i) => (
            <tr key={i} className="border-t border-gray-700">
              <td className="p-3 text-gray-400">
                {new Date(alert.time).toLocaleString()}
              </td>
              <td className="p-3">{alert.device_id}</td>
              <td className="p-3 text-red-400">
                {(alert.probability * 100).toFixed(1)}%
              </td>
              <td className="p-3 text-gray-300 capitalize">{alert.channel}</td>
              <td className="p-3">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    alert.status === "sent"
                      ? "bg-green-600/20 text-green-400"
                      : alert.status === "skipped"
                      ? "bg-yellow-600/20 text-yellow-400"
                      : "bg-red-600/20 text-red-400"
                  }`}
                >
                  {alert.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default AlertHistory;
