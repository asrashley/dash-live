export const initialTokens = {
  accessToken: {
    expires: "2025-01-07T22:06:17.130812Z",
    jti: "eyJhbGciOiJIUzI1NiIsVCJ9.eyJmcmVzaCI6ZmFsc2UsImlqkKVvSYHTYyuY",
  },
  csrfTokens: {
    files: null,
    kids: null,
    streams: "67676f9ndfvdfgaQNY1juxc2oIpHvgKAgil6LAs%3D%27",
    upload: null,
  },
  refreshToken: null,
};

export const navbar = [
  {
    active: true,
    className: "spa",
    href: "/",
    title: "Home",
  },
  {
    active: false,
    className: "",
    href: "/streams",
    title: "Streams",
  },
  {
    active: false,
    className: "spa",
    href: "/multi-period-streams",
    title: "Multi-Period",
  },
  {
    active: false,
    className: "",
    href: "/validate/",
    title: "Validate",
  },
  {
    active: false,
    className: "",
    href: "/media/inspect",
    title: "Inspect",
  },
  {
    active: false,
    className: "user-login",
    href: "/login",
    title: "Log In",
  },
];

export const user = {
  groups: [],
  isAuthenticated: false,
  pk: 3,
  username: "_AnonymousUser_",
};
