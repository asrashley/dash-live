import { DecoratedStream } from "./DecoratedStream";

export interface ConfirmDeleteDialogState {
    name: string;
    confirmed: boolean;
}

export interface MpsOptionsDialogState {
    options: object;
    lastModified: number;
    name: string;
}

export interface TrackPickerDialogState {
    pk: number | string;
    pid: string;
    guest: boolean;
    stream: DecoratedStream;
}

export interface DialogState {
    backdrop: boolean;
    confirmDelete?: ConfirmDeleteDialogState;
    mpsOptions?: MpsOptionsDialogState;
    trackPicker?: TrackPickerDialogState;
}