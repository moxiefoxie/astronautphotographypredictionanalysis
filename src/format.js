// Display precision only. Scientific source data and exports remain untouched.
export const formatMeasurement = value => value == null || !Number.isFinite(Number(value))
  ? 'Not available' : Number(value).toLocaleString(undefined, { maximumSignificantDigits: 1 });
export const formatCount = value => value == null ? 'Not available' : Number(value).toLocaleString();
export const formatCoordinate = value => value == null ? 'Not available' : Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });
