
import React from "react";
import ReactDOM from "react-dom/client";
import { Amplify } from "aws-amplify";
import App from "./App";
import "./index.css";

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: "ap-south-1_hPEHDLIai",
      userPoolClientId: "22t68sngdl24q7m1och3ihsab4",
      loginWith: {
        email: true,
      },
    },
  },
});

ReactDOM.createRoot(
  document.getElementById("root")!
).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
