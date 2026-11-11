const CROP_KEY = "agrisense_crop_result";
const MOISTURE_KEY = "agrisense_moisture_result";

interface CachedAnalysis<T> {
  fieldId: string;
  result: T;
  cachedAt: string;
}

function readCache<T>(key: string, fieldId: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as CachedAnalysis<T> | T;
    if (parsed && typeof parsed === "object" && "fieldId" in parsed && "result" in parsed) {
      return parsed.fieldId === fieldId ? parsed.result : null;
    }

    return parsed as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

function writeCache<T>(key: string, fieldId: string, result: T): void {
  const payload: CachedAnalysis<T> = {
    fieldId,
    result,
    cachedAt: new Date().toISOString(),
  };
  localStorage.setItem(key, JSON.stringify(payload));
}

export function getCachedCropResult(fieldId: string): any | null {
  return readCache<any>(CROP_KEY, fieldId);
}

export function setCachedCropResult(fieldId: string, result: any): void {
  writeCache(CROP_KEY, fieldId, result);
}

export function getCachedMoistureResult(fieldId: string): any | null {
  return readCache<any>(MOISTURE_KEY, fieldId);
}

export function setCachedMoistureResult(fieldId: string, result: any): void {
  writeCache(MOISTURE_KEY, fieldId, result);
}

export function hasCachedCropResult(fieldId: string): boolean {
  return getCachedCropResult(fieldId) !== null;
}

export function hasCachedMoistureResult(fieldId: string): boolean {
  return getCachedMoistureResult(fieldId) !== null;
}

export function clearAnalysisCacheForField(fieldId: string): void {
  [CROP_KEY, MOISTURE_KEY].forEach((key) => {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed?.fieldId === fieldId) {
        localStorage.removeItem(key);
      }
    } catch {
      localStorage.removeItem(key);
    }
  });
}
