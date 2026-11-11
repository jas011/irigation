const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

class ApiService {
  private static getHeaders(contentType: string = "application/json"): HeadersInit {
    const headers: HeadersInit = {};
    if (contentType) {
      headers["Content-Type"] = contentType;
    }
    const token = localStorage.getItem("agrisense_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  private static async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage = "An error occurred during the request.";
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch (e) {
        // Response was not JSON
      }
      throw new Error(errorMessage);
    }
    
    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // --- AUTHENTICATION ---
  
  static async login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    const data = await this.handleResponse<{ access_token: string; token_type: string }>(res);
    localStorage.setItem("agrisense_token", data.access_token);
    return data;
  }

  static async register(name: string, email: string, password: string, confirmPassword: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        name,
        email,
        password,
        confirm_password: confirmPassword,
      }),
    });
    return this.handleResponse(res);
  }

  static async getMe(): Promise<{ id: number; name: string; email: string; created_at: string }> {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  static async changePassword(oldPassword: string, newPassword: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/auth/change-password`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword,
      }),
    });
    return this.handleResponse(res);
  }

  static logout(): void {
    localStorage.removeItem("agrisense_token");
  }

  static isAuthenticated(): boolean {
    return !!localStorage.getItem("agrisense_token");
  }

  // --- FIELDS MANAGEMENT ---

  static async validateField(geometry: any): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/fields/validate`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ geometry }),
    });
    return this.handleResponse(res);
  }

  static async verifyFieldAI(
    geometry: any,
    imageBase64?: string
  ): Promise<{
    is_field: boolean;
    confidence: number;
    land_type: string;
    reason: string;
    user_friendly_category?: string;
    all_possibilities?: Record<string, number>;
    visual_features_observed?: string[];
    details?: any;
  }> {
    const res = await fetch(`${API_BASE_URL}/fields/verify-ai`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        geometry,
        image_base64: imageBase64 || null,
      }),
    });
    return this.handleResponse(res);
  }

  static async createField(geometry: any, location?: any): Promise<any> {

    const res = await fetch(`${API_BASE_URL}/fields`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ geometry, location }),
    });
    return this.handleResponse(res);
  }

  static async listFields(): Promise<any[]> {
    const res = await fetch(`${API_BASE_URL}/fields`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  static async getField(fieldId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/fields/${fieldId}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  static async updateField(fieldId: string, location: any): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/fields/${fieldId}`, {
      method: "PUT",
      headers: this.getHeaders(),
      body: JSON.stringify(location),
    });
    return this.handleResponse(res);
  }

  static async deleteField(fieldId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/fields/${fieldId}`, {
      method: "DELETE",
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  static async getCurrentSeason(): Promise<{
    season_name: string;
    season_type: string;
    year: string;
    description: string;
    source?: string;
  }> {
    const res = await fetch(`${API_BASE_URL}/analysis/current-season`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }

  // --- STAGE 2 & 3 ANALYSIS ---
  static async analyzeCropStage(fieldId: string, geometry: any): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/analysis/crop`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        field_id: fieldId,
        geometry,
      }),
    });
    return this.handleResponse(res);
  }

  static async analyzeMoistureStage(fieldId: string, geometry: any, cropPrediction: string, growthStage: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/analysis/moisture`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        field_id: fieldId,
        geometry,
        crop_prediction: cropPrediction,
        growth_stage: growthStage,
      }),
    });
    return this.handleResponse(res);
  }

  // --- WEATHER INTELLIGENCE ---
  static async getWeatherForecast(
    latitude: number,
    longitude: number,
    forceRefresh: boolean = false,
    fieldId?: string | null
  ): Promise<any> {
    const params = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
      refresh: forceRefresh ? "true" : "false",
    });
    if (fieldId) {
      params.append("field_id", fieldId);
    }
    const res = await fetch(`${API_BASE_URL}/weather/forecast?${params.toString()}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse(res);
  }
}

export default ApiService;
