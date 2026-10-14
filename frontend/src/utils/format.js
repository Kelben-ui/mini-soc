export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
    return "—";
  }

  const total = Math.max(0, Math.round(Number(seconds)));

  if (total < 60) return `${total}s`;

  const minutes = Math.floor(total / 60);
  const restSeconds = total % 60;
  if (minutes < 60) {
    return restSeconds ? `${minutes}m ${restSeconds}s` : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours < 24) {
    return restMinutes ? `${hours}h ${restMinutes}m` : `${hours}h`;
  }

  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days}d ${restHours}h` : `${days}d`;
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";

  const value = Number(bytes);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDateTime(value) {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);

  return date.toLocaleString();
}
