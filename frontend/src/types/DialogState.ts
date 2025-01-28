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

export interface AddUserDialogState {
    active: boolean;
}

export interface DialogState {
    backdrop: boolean;
    addUser?: AddUserDialogState;
    confirmDelete?: ConfirmDeleteDialogState;
    mpsOptions?: MpsOptionsDialogState;
    trackPicker?: TrackPickerDialogState;
}