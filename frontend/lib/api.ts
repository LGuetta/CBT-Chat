/**
 * API client for CBT Chat Assistant backend
 */

import axios, { AxiosInstance } from "axios";
import {
  ChatResponse,
  Session,
  Message,
  TherapistDashboard,
  SessionTranscript,
  PatientOverview,
  SkillCompletion,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        "Content-Type": "application/json",
      },
      timeout: 30000,
    });
  }

  // ============================================================================
  // PATIENT / CHAT ENDPOINTS
  // ============================================================================

  async createSession(accessCode: string, sessionGoal?: string): Promise<Session> {
    const response = await this.client.post("/api/chat/session/create", {
      patient_access_code: accessCode,
      session_goal: sessionGoal,
    });
    return response.data;
  }

  async sendMessage(
    accessCode: string,
    message: string,
    sessionId?: string
  ): Promise<ChatResponse> {
    const response = await this.client.post("/api/chat/message", {
      patient_access_code: accessCode,
      message,
      session_id: sessionId,
    });
    return response.data;
  }

  async endSession(sessionId: string, accessCode: string): Promise<void> {
    await this.client.post("/api/chat/session/end", {
      session_id: sessionId,
      patient_access_code: accessCode,
    });
  }

  async getSessionHistory(
    sessionId: string,
    accessCode: string
  ): Promise<Message[]> {
    const response = await this.client.get(
      `/api/chat/session/${sessionId}/history`,
      {
        params: { access_code: accessCode },
      }
    );
    return response.data;
  }

  async reloadPrompts(): Promise<void> {
    await this.client.post("/api/chat/prompts/reload");
  }

  // ============================================================================
  // THERAPIST ENDPOINTS
  // ============================================================================

  async getTherapistDashboard(email: string): Promise<TherapistDashboard> {
    const response = await this.client.get(`/api/therapist/dashboard/${email}`);
    return response.data;
  }

  async getSessionTranscript(
    sessionId: string,
    therapistEmail: string
  ): Promise<SessionTranscript> {
    const response = await this.client.get(
      `/api/therapist/session/${sessionId}/transcript`,
      {
        params: { therapist_email: therapistEmail },
      }
    );
    return response.data;
  }

  async getPatientSessions(
    patientId: string,
    therapistEmail: string,
    limit: number = 20
  ): Promise<Session[]> {
    const response = await this.client.get(
      `/api/therapist/patient/${patientId}/sessions`,
      {
        params: { therapist_email: therapistEmail, limit },
      }
    );
    return response.data;
  }

  async getPatientSkills(
    patientId: string,
    therapistEmail: string,
    skillType?: string,
    limit: number = 50
  ): Promise<SkillCompletion[]> {
    const response = await this.client.get(
      `/api/therapist/patient/${patientId}/skills`,
      {
        params: {
          therapist_email: therapistEmail,
          skill_type: skillType,
          limit,
        },
      }
    );
    return response.data;
  }

  async reviewRiskEvent(
    riskEventId: string,
    therapistEmail: string,
    notes?: string
  ): Promise<void> {
    await this.client.post(
      `/api/therapist/risk-event/${riskEventId}/review`,
      null,
      {
        params: { therapist_email: therapistEmail, notes },
      }
    );
  }

  async getPatientSummary(
    patientId: string,
    therapistEmail: string,
    periodDays: number = 7
  ): Promise<any> {
    const response = await this.client.get(
      `/api/therapist/patient/${patientId}/summary`,
      {
        params: { therapist_email: therapistEmail, period_days: periodDays },
      }
    );
    return response.data;
  }

  async exportPatientDataJSON(
    patientId: string,
    therapistEmail: string
  ): Promise<Blob> {
    const response = await this.client.get(
      `/api/therapist/patient/${patientId}/export/json`,
      {
        params: { therapist_email: therapistEmail },
        responseType: "blob",
      }
    );
    return response.data;
  }

  async exportPatientDataCSV(
    patientId: string,
    therapistEmail: string
  ): Promise<Blob> {
    const response = await this.client.get(
      `/api/therapist/patient/${patientId}/export/csv`,
      {
        params: { therapist_email: therapistEmail },
        responseType: "blob",
      }
    );
    return response.data;
  }

  // ============================================================================
  // ADMIN ENDPOINTS
  // ============================================================================

  async createTestPatient(
    preferredName: string,
    countryCode: string = "US"
  ): Promise<{ access_code: string; patient: any }> {
    const response = await this.client.post("/api/admin/test-patient/create", {
      preferred_name: preferredName,
      country_code: countryCode,
    });
    return response.data;
  }
}

export const apiClient = new APIClient();
