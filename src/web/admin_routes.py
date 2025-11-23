"""
Admin authentication routes for the Westside LA Events app.
"""

from fasthtml.common import *
from src.web.security import (
    hash_password, verify_password, get_admin_password_hash,
    ADMIN_USERNAME, sanitize_input
)


def setup_admin_routes(app, rt):
    """Setup admin authentication routes."""

    @rt('/admin/login')
    def get(request, session, redirect: str = '/admin/analytics'):
        """Admin login page."""
        # If already authenticated, redirect to destination
        if session.get('admin_authenticated'):
            return RedirectResponse(url=redirect, status_code=303)

        return Html(
            Head(
                Title('Admin Login - Westside LA Events'),
                Meta(charset='utf-8'),
                Meta(name='viewport', content='width=device-width, initial-scale=1'),
                Link(rel='stylesheet', href='/static/css/style.css'),
                Style("""
                    .login-container {
                        max-width: 400px;
                        margin: 100px auto;
                        padding: 40px;
                        background: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }
                    .login-container h1 {
                        margin-bottom: 30px;
                        text-align: center;
                        color: #333;
                    }
                    .login-form {
                        display: flex;
                        flex-direction: column;
                        gap: 20px;
                    }
                    .form-group {
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                    }
                    .form-group label {
                        font-weight: 600;
                        color: #555;
                    }
                    .form-group input {
                        padding: 12px;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        font-size: 16px;
                    }
                    .form-group input:focus {
                        outline: none;
                        border-color: #007bff;
                    }
                    .login-button {
                        padding: 14px;
                        background: #007bff;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 16px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: background 0.2s;
                    }
                    .login-button:hover {
                        background: #0056b3;
                    }
                    .error-message {
                        padding: 12px;
                        background: #fee;
                        color: #c33;
                        border-radius: 4px;
                        text-align: center;
                    }
                    .info-message {
                        padding: 12px;
                        background: #e3f2fd;
                        color: #1976d2;
                        border-radius: 4px;
                        font-size: 14px;
                        margin-top: 20px;
                        text-align: center;
                    }
                    .back-link {
                        text-align: center;
                        margin-top: 20px;
                    }
                    .back-link a {
                        color: #007bff;
                        text-decoration: none;
                    }
                """)
            ),
            Body(
                Div(
                    H1('🔒 Admin Login'),
                    Form(
                        Div(
                            Label('Username', _for='username'),
                            Input(
                                type='text',
                                id='username',
                                name='username',
                                required=True,
                                autocomplete='username'
                            ),
                            cls='form-group'
                        ),
                        Div(
                            Label('Password', _for='password'),
                            Input(
                                type='password',
                                id='password',
                                name='password',
                                required=True,
                                autocomplete='current-password'
                            ),
                            cls='form-group'
                        ),
                        Input(type='hidden', name='redirect', value=redirect),
                        Button('Login', type='submit', cls='login-button'),
                        cls='login-form',
                        method='POST',
                        action='/admin/login'
                    ),
                    Div(
                        P(
                            Strong('Development Mode:'),
                            Br(),
                            'Username: admin',
                            Br(),
                            'Password: admin123',
                            Br(),
                            Br(),
                            Small('⚠️ Change these credentials in production!'),
                            cls='info-message'
                        )
                    ) if not get_admin_password_hash() else None,
                    Div(
                        A('← Back to Home', href='/'),
                        cls='back-link'
                    ),
                    cls='login-container'
                )
            )
        )

    @rt('/admin/login')
    async def post(request, session):
        """Handle admin login form submission."""
        form_data = await request.form()
        username = sanitize_input(form_data.get('username', ''), max_length=50)
        password = form_data.get('password', '')
        redirect_url = sanitize_input(form_data.get('redirect', '/admin/analytics'), max_length=200)

        # Verify credentials
        password_hash = get_admin_password_hash()
        if username == ADMIN_USERNAME and verify_password(password, password_hash):
            # Set session
            session['admin_authenticated'] = True
            session['admin_username'] = username

            # Redirect to destination
            return RedirectResponse(url=redirect_url, status_code=303)
        else:
            # Login failed - show error
            return Html(
                Head(
                    Title('Admin Login - Westside LA Events'),
                    Meta(charset='utf-8'),
                    Meta(name='viewport', content='width=device-width, initial-scale=1'),
                    Link(rel='stylesheet', href='/static/css/style.css'),
                    Style("""
                        .login-container {
                            max-width: 400px;
                            margin: 100px auto;
                            padding: 40px;
                            background: white;
                            border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        }
                        .login-container h1 {
                            margin-bottom: 30px;
                            text-align: center;
                            color: #333;
                        }
                        .login-form {
                            display: flex;
                            flex-direction: column;
                            gap: 20px;
                        }
                        .form-group {
                            display: flex;
                            flex-direction: column;
                            gap: 8px;
                        }
                        .form-group label {
                            font-weight: 600;
                            color: #555;
                        }
                        .form-group input {
                            padding: 12px;
                            border: 1px solid #ddd;
                            border-radius: 4px;
                            font-size: 16px;
                        }
                        .form-group input:focus {
                            outline: none;
                            border-color: #007bff;
                        }
                        .login-button {
                            padding: 14px;
                            background: #007bff;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            font-size: 16px;
                            font-weight: 600;
                            cursor: pointer;
                            transition: background 0.2s;
                        }
                        .login-button:hover {
                            background: #0056b3;
                        }
                        .error-message {
                            padding: 12px;
                            background: #fee;
                            color: #c33;
                            border-radius: 4px;
                            text-align: center;
                        }
                        .back-link {
                            text-align: center;
                            margin-top: 20px;
                        }
                        .back-link a {
                            color: #007bff;
                            text-decoration: none;
                        }
                    """)
                ),
                Body(
                    Div(
                        H1('🔒 Admin Login'),
                        Div('Invalid username or password. Please try again.', cls='error-message'),
                        Form(
                            Div(
                                Label('Username', _for='username'),
                                Input(
                                    type='text',
                                    id='username',
                                    name='username',
                                    value=username,
                                    required=True,
                                    autocomplete='username'
                                ),
                                cls='form-group'
                            ),
                            Div(
                                Label('Password', _for='password'),
                                Input(
                                    type='password',
                                    id='password',
                                    name='password',
                                    required=True,
                                    autocomplete='current-password'
                                ),
                                cls='form-group'
                            ),
                            Input(type='hidden', name='redirect', value=redirect_url),
                            Button('Login', type='submit', cls='login-button'),
                            cls='login-form',
                            method='POST',
                            action='/admin/login'
                        ),
                        Div(
                            A('← Back to Home', href='/'),
                            cls='back-link'
                        ),
                        cls='login-container'
                    )
                )
            )

    @rt('/admin/logout')
    def get(request, session):
        """Admin logout."""
        session.pop('admin_authenticated', None)
        session.pop('admin_username', None)
        return RedirectResponse(url='/', status_code=303)
