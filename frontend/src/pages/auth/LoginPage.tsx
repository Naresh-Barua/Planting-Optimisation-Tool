import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { useState } from "react";

function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState({
    email: false,
    password: false,
  });

  const emailError =
    touched.email && !email.trim() ? "Email is required." : "";
  const passwordError =
    touched.password && !password.trim() ? "Password is required." : "";

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setTouched({
      email: true,
      password: true,
    });

    if (!email.trim() || !password.trim()) {
      return;
    }

    // Backend integration will be added later
    console.log("Login UI submitted:", { email, password });
  };

  const isDisabled = !email.trim() || !password.trim();
  return (
    <>
      <Helmet>
        <title>Login | Planting Optimisation Tool</title>
      </Helmet>

      <main className="login-page">
        <section className="login-card">
          <div className="login-card-header">
            <span className="login-badge">Admin Access</span>
            <h1 className="login-title">Sign in to continue</h1>
            <p className="login-subtitle">
              Access the management workspace for dashboard tools, settings, and
              future administrative features.
            </p>
          </div>

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="login-form-group">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                className={`login-input ${emailError ? "login-input-error" : ""}`}
                placeholder="Enter your email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                onBlur={() =>
                  setTouched((previous) => ({
                    ...previous,
                    email: true,
                  }))
                }
              />
              {emailError ? (
                <p className="login-field-error">{emailError}</p>
              ) : null}
            </div>

            <div className="login-form-group">
              <label htmlFor="password">Password</label>

              <div className="login-password-wrapper">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  className={`login-input login-password-input ${passwordError ? "login-input-error" : ""}`}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  onBlur={() =>
                    setTouched((previous) => ({
                      ...previous,
                      password: true,
                    }))
                  }
                />

                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() => setShowPassword((previous) => !previous)}
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>

              {passwordError ? (
                <p className="login-field-error">{passwordError}</p>
              ) : null}
            </div>

            <div className="login-form-meta">
              <label className="login-checkbox-row">
                <input type="checkbox" />
                <span>Remember me</span>
              </label>

              <Link to="/forgot-password" className="login-link">
                Forgot password?
              </Link>
            </div>

            <div className="login-message login-message-placeholder">
              Authentication will be connected in the next step.
            </div>

            <button type="submit" className="login-submit-btn" disabled={isDisabled}>
                Sign in
            </button>
          </form>
        </section>
      </main>
    </>
  );
}

export default LoginPage;