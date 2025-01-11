export interface MultiPeriodStreamValidationRequest {
    name: string | null;
    title: string | null;
    pk: string | number | null;
}

export interface MultiPeriodStreamValidationResponse {
    errors: {
        name?: string;
        title?: string;
        pk?: string;
    }
}