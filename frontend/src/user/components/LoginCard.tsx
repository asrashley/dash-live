import { useCallback } from "preact/hooks";
import { type ReadonlySignal, useComputed, useSignal } from "@preact/signals";

import { Card } from "../../components/Card";
import { InputFieldRow } from "../../components/InputFieldRow";

import { SetValueFunc } from "../../types/SetValueFunc";
import { LoginRequest } from "../../types/LoginRequest";
import { InputFormData } from "../../types/InputFormData";

function LoginError({error}: { error: ReadonlySignal<string | undefined>}) {
	const className = useComputed<string>(() => error.value ? "alert alert-danger": "d-none");

	return <div className={className} role="alert">{ error.value ?? ''}</div>;
}

export interface LoginCardProps {
  error: ReadonlySignal<string | undefined>;
  submitting: ReadonlySignal<boolean>;
  onLogin: (request: LoginRequest) => void;
}
export function LoginCard({ error, submitting, onLogin }: LoginCardProps) {
  const data = useSignal<InputFormData>({
    username: "",
    password: "",
    rememberme: false,
  });
  const disabledFields = useSignal<Record<string, boolean>>({});
  const className = useComputed<string>(() => submitting.value ? "opacity-25": "");
  const disableSubmit = useComputed<boolean>(() => submitting.value || data.value.username === "" || data.value.password === "");
  const header = useComputed<string>(() => submitting.value ? "Logging into DASH server..." : "Log into DASH server");
  const setValue: SetValueFunc = useCallback(
    (name, value) => {
      data.value = {
        ...data.value,
        [name]: value,
      };
    },
    [data]
  );
  const onSubmit = useCallback((ev: Event) => {
	  ev.preventDefault();
	  onLogin(data.value as unknown as LoginRequest);
  }, [data, onLogin]);

  return (
    <Card id="login" header={header}>
      <form id="login-form" name="login" onSubmit={onSubmit}  className={className}>
		<LoginError error={error} />
        <InputFieldRow
          type="text"
          name="username"
          title="Username"
          shortName=""
          fullName=""
          mode="cgi"
          data={data}
          disabledFields={disabledFields}
          setValue={setValue}
        />
        <InputFieldRow
          type="password"
          name="password"
          title="Password"
          shortName=""
          fullName=""
          mode="cgi"
          data={data}
          disabledFields={disabledFields}
          setValue={setValue}
        />
        <InputFieldRow
          type="checkbox"
          name="rememberme"
          title="Remember Me"
          shortName=""
          fullName=""
          mode="cgi"
          data={data}
          disabledFields={disabledFields}
          setValue={setValue}
        />
        <div>
          <button type="submit" className="btn btn-primary" disabled={disableSubmit} >
            Login
          </button>
        </div>
      </form>
    </Card>
  );
}
