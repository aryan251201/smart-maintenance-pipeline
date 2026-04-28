function DeviceCard({ prediction, selected, onClick }) {
  const { device_id, failure_predicted, failure_probability, estimated_time_to_failure } =
    prediction;

  const isError = prediction.error;
  const statusColor = isError
    ? "border-gray-600"
    : failure_predicted
    ? "border-red-500 bg-red-500/10"
    : "border-green-500 bg-green-500/10";

  return (
    <div
      onClick={onClick}
      className={`rounded-lg border-2 p-4 cursor-pointer transition-all ${statusColor} ${
        selected ? "ring-2 ring-blue-400" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-lg">{device_id}</h3>
        <span
          className={`text-sm font-medium px-2 py-1 rounded ${
            isError
              ? "bg-gray-700 text-gray-300"
              : failure_predicted
              ? "bg-red-600 text-white"
              : "bg-green-600 text-white"
          }`}
        >
          {isError ? "NO DATA" : failure_predicted ? "ALERT" : "HEALTHY"}
        </span>
      </div>

      {!isError && (
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Failure probability</span>
            <span className={failure_predicted ? "text-red-400 font-medium" : "text-green-400"}>
              {(failure_probability * 100).toFixed(1)}%
            </span>
          </div>
          {failure_predicted && estimated_time_to_failure && (
            <div className="flex justify-between">
              <span className="text-gray-400">Time to failure</span>
              <span className="text-red-400 font-medium">{estimated_time_to_failure}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DeviceCard;
