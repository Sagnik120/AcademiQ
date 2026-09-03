/**
 * AcademiQ — API Client Engine with Bearer Token Injection
 */

const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  getToken() {
    return localStorage.getItem('academiq_access_token');
  }

  getHeaders(isMultipart = false) {
    const headers = {};
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (!isMultipart) {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = { ...this.getHeaders(options.isMultipart), ...(options.headers || {}) };
    
    if (options.isMultipart) {
      delete headers['Content-Type'];
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers
      });

      // Handle 401 Unauthorized
      if (response.status === 401) {
        // Clear expired session if not on an auth page
        if (!window.location.pathname.includes('/auth/')) {
          localStorage.removeItem('academiq_access_token');
          localStorage.removeItem('academiq_user');
          window.location.href = '/auth/learner-login.html?expired=true';
        }
      }

      // Check if response has content
      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorDetail = (data && data.detail) 
          ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
          : response.statusText || 'An unexpected error occurred';
        throw new Error(errorDetail);
      }

      return data;
    } catch (err) {
      console.error(`API Request Error [${endpoint}]:`, err);
      throw err;
    }
  }

  get(endpoint, params = {}) {
    const query = new URLSearchParams(params).toString();
    const fullEndpoint = query ? `${endpoint}?${query}` : endpoint;
    return this.request(fullEndpoint, { method: 'GET' });
  }

  post(endpoint, body = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  patch(endpoint, body = {}) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(body)
    });
  }

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }

  upload(endpoint, formData) {
    return this.request(endpoint, {
      method: 'POST',
      body: formData,
      isMultipart: true
    });
  }
}

const api = new ApiClient(API_BASE_URL);
