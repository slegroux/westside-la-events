"""
Analytics dashboard routes for LA Events Aggregator.
"""

from fasthtml.common import *
from datetime import datetime, timedelta
from typing import Optional
import config
from src.web.security import check_admin_auth


def analytics_page_head(title: str):
    """Page head for analytics dashboard."""
    return Head(
        Title(title),
        Meta(charset='UTF-8'),
        Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
        Meta(name='robots', content='noindex, nofollow'),  # Don't index analytics
        Link(rel='stylesheet', href='/static/css/style.css'),
        # Chart.js for visualizations
        Script(src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'),
        Style('''
            .analytics-container {
                max-width: 1400px;
                margin: 2rem auto;
                padding: 0 2rem;
            }
            .analytics-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 2rem;
                border-radius: 1rem;
                margin-bottom: 2rem;
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }
            .metric-card {
                background: white;
                padding: 1.5rem;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                border-left: 4px solid #667eea;
            }
            .metric-value {
                font-size: 2.5rem;
                font-weight: 800;
                color: #667eea;
                margin: 0.5rem 0;
            }
            .metric-label {
                font-size: 0.875rem;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                font-weight: 600;
            }
            .metric-change {
                font-size: 0.875rem;
                font-weight: 600;
                margin-top: 0.5rem;
            }
            .metric-change.positive {
                color: #10b981;
            }
            .metric-change.negative {
                color: #ef4444;
            }
            .chart-container {
                background: white;
                padding: 2rem;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 2rem;
            }
            .chart-title {
                font-size: 1.25rem;
                font-weight: 700;
                margin-bottom: 1.5rem;
                color: #1e293b;
            }
            .data-table {
                background: white;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            .data-table table {
                width: 100%;
                border-collapse: collapse;
            }
            .data-table th {
                background: #f8fafc;
                padding: 1rem;
                text-align: left;
                font-weight: 700;
                color: #1e293b;
                border-bottom: 2px solid #e2e8f0;
            }
            .data-table td {
                padding: 1rem;
                border-bottom: 1px solid #e2e8f0;
            }
            .data-table tr:hover {
                background: #f8fafc;
            }
            .date-range-selector {
                display: flex;
                gap: 1rem;
                align-items: center;
                margin-bottom: 2rem;
            }
            .date-range-selector button {
                padding: 0.75rem 1.5rem;
                background: white;
                border: 2px solid #e2e8f0;
                border-radius: 0.5rem;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s;
            }
            .date-range-selector button.active {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-color: transparent;
            }
            .date-range-selector button:hover:not(.active) {
                border-color: #667eea;
            }
        ''')
    )


def metric_card(label: str, value: str, change: Optional[str] = None, change_positive: bool = True):
    """Render a metric card."""
    change_elem = None
    if change:
        change_class = 'metric-change positive' if change_positive else 'metric-change negative'
        arrow = '↑' if change_positive else '↓'
        change_elem = Div(f'{arrow} {change}', cls=change_class)

    return Div(
        Div(label, cls='metric-label'),
        Div(value, cls='metric-value'),
        change_elem,
        cls='metric-card'
    )


def chart_container(title: str, chart_id: str):
    """Render a chart container."""
    return Div(
        H3(title, cls='chart-title'),
        Canvas(id=chart_id, style='max-height: 400px;'),
        cls='chart-container'
    )


def data_table(title: str, headers: list, rows: list):
    """Render a data table."""
    return Div(
        H3(title, cls='chart-title', style='padding: 1.5rem 1.5rem 0;'),
        Table(
            Thead(
                Tr(*[Th(h) for h in headers])
            ),
            Tbody(
                *[Tr(*[Td(str(cell)) for cell in row]) for row in rows]
            )
        ),
        cls='data-table'
    )


def setup_analytics_routes(app, rt, state):
    """Setup analytics dashboard routes."""

    @rt('/admin/analytics')
    def analytics_dashboard(request, session, days: int = 7):
        """Main analytics dashboard."""
        # Require authentication
        if not check_admin_auth(request):
            return RedirectResponse(
                url='/admin/login?redirect=/admin/analytics',
                status_code=303
            )

        if not config.ENABLE_ANALYTICS or not state.analytics:
            return Html(
                analytics_page_head('Analytics Disabled'),
                Body(
                    Div(
                        H1('Analytics Disabled'),
                        P('Analytics tracking is currently disabled. Enable it in config.py'),
                        cls='analytics-container'
                    )
                )
            )

        # Get metrics for the selected date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get current period metrics
        current_metrics = state.analytics.get_date_range_metrics(start_date, end_date)
        total_visitors = sum(m['unique_visitors'] for m in current_metrics)
        total_page_views = sum(m['page_views'] for m in current_metrics)
        total_events_viewed = sum(m['events_viewed'] for m in current_metrics)
        total_events_clicked = sum(m['events_clicked'] for m in current_metrics)
        total_searches = sum(m['searches'] for m in current_metrics)
        total_favorites = sum(m['favorites_added'] for m in current_metrics)

        # Calculate click-through rate
        ctr = round((total_events_clicked / total_events_viewed * 100) if total_events_viewed > 0 else 0, 1)

        # Get session stats
        session_stats = state.analytics.get_session_stats(days=days)

        # Get popular events
        popular_events = state.analytics.get_popular_events(limit=10, days=days)
        popular_events_rows = []
        for event_id, views, clicks in popular_events:
            event = state.db.get_event(event_id)
            if event:
                event_ctr = round((clicks / views * 100) if views > 0 else 0, 1)
                popular_events_rows.append([
                    event.title[:50] + '...' if len(event.title) > 50 else event.title,
                    views,
                    clicks,
                    f'{event_ctr}%'
                ])

        # Get popular searches
        popular_searches = state.analytics.get_popular_searches(limit=10, days=days)
        search_rows = [[query[:50] + '...' if len(query) > 50 else query, count] for query, count in popular_searches]

        # Get category popularity
        category_stats = state.analytics.get_category_popularity(days=days)
        category_rows = [[cat, count] for cat, count in category_stats]

        # Get source performance
        source_perf = state.analytics.get_source_performance(days=days)
        source_rows = [
            [s['source'], s['views'], s['clicks'], s['favorites'], f"{s['click_through_rate']}%"]
            for s in source_perf
        ]

        # Prepare chart data
        chart_labels = [m['date'] for m in current_metrics]
        visitors_data = [m['unique_visitors'] for m in current_metrics]
        pageviews_data = [m['page_views'] for m in current_metrics]
        events_viewed_data = [m['events_viewed'] for m in current_metrics]
        events_clicked_data = [m['events_clicked'] for m in current_metrics]

        return Html(
            analytics_page_head('Analytics Dashboard - Westside LA Events'),
            Body(
                Div(
                    # Header
                    Div(
                        H1('📊 Analytics Dashboard'),
                        P(f'Showing data for the last {days} days', style='opacity: 0.9; margin-top: 0.5rem;'),
                        cls='analytics-header'
                    ),

                    # Date range selector
                    Div(
                        Button('Last 7 Days', cls='active' if days == 7 else '',
                               hx_get='/admin/analytics?days=7', hx_target='body', hx_swap='outerHTML'),
                        Button('Last 30 Days', cls='active' if days == 30 else '',
                               hx_get='/admin/analytics?days=30', hx_target='body', hx_swap='outerHTML'),
                        Button('Last 90 Days', cls='active' if days == 90 else '',
                               hx_get='/admin/analytics?days=90', hx_target='body', hx_swap='outerHTML'),
                        cls='date-range-selector'
                    ),

                    # Key metrics
                    Div(
                        metric_card('Unique Visitors', str(total_visitors)),
                        metric_card('Page Views', str(total_page_views)),
                        metric_card('Events Viewed', str(total_events_viewed)),
                        metric_card('Events Clicked', str(total_events_clicked)),
                        metric_card('Click-Through Rate', f'{ctr}%'),
                        metric_card('Searches', str(total_searches)),
                        cls='metrics-grid'
                    ),

                    # Session stats
                    Div(
                        metric_card('Total Sessions', str(session_stats['total_sessions'])),
                        metric_card('Avg Pages/Session', str(session_stats['avg_page_views'])),
                        metric_card('Avg Events/Session', str(session_stats['avg_events_viewed'])),
                        metric_card('Bounce Rate', f"{session_stats['bounce_rate']}%", change_positive=False),
                        cls='metrics-grid'
                    ),

                    # Charts
                    chart_container('Daily Visitors', 'visitors-chart'),
                    chart_container('Event Interactions', 'interactions-chart'),

                    # Tables
                    data_table('Top Events', ['Event', 'Views', 'Clicks', 'CTR'], popular_events_rows) if popular_events_rows else None,
                    data_table('Popular Searches', ['Query', 'Count'], search_rows) if search_rows else None,
                    data_table('Category Popularity', ['Category', 'Interactions'], category_rows) if category_rows else None,
                    data_table('Source Performance', ['Source', 'Views', 'Clicks', 'Favorites', 'CTR'], source_rows) if source_rows else None,

                    # Chart initialization scripts
                    Script(f'''
                        // Visitors Chart
                        new Chart(document.getElementById('visitors-chart'), {{
                            type: 'line',
                            data: {{
                                labels: {chart_labels},
                                datasets: [{{
                                    label: 'Unique Visitors',
                                    data: {visitors_data},
                                    borderColor: 'rgb(102, 126, 234)',
                                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                }}, {{
                                    label: 'Page Views',
                                    data: {pageviews_data},
                                    borderColor: 'rgb(118, 75, 162)',
                                    backgroundColor: 'rgba(118, 75, 162, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                }}]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: true,
                                plugins: {{
                                    legend: {{
                                        position: 'top',
                                    }}
                                }},
                                scales: {{
                                    y: {{
                                        beginAtZero: true
                                    }}
                                }}
                            }}
                        }});

                        // Interactions Chart
                        new Chart(document.getElementById('interactions-chart'), {{
                            type: 'bar',
                            data: {{
                                labels: {chart_labels},
                                datasets: [{{
                                    label: 'Events Viewed',
                                    data: {events_viewed_data},
                                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                                }}, {{
                                    label: 'Events Clicked',
                                    data: {events_clicked_data},
                                    backgroundColor: 'rgba(16, 185, 129, 0.8)',
                                }}]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: true,
                                plugins: {{
                                    legend: {{
                                        position: 'top',
                                    }}
                                }},
                                scales: {{
                                    y: {{
                                        beginAtZero: true
                                    }}
                                }}
                            }}
                        }});
                    '''),

                    # HTMX
                    Script(src='https://unpkg.com/htmx.org@2.0.3'),

                    cls='analytics-container'
                )
            )
        )

    @rt('/admin/analytics/api')
    def analytics_api(request, days: int = 7):
        """API endpoint for analytics data."""
        from starlette.responses import JSONResponse

        # Require authentication
        if not check_admin_auth(request):
            return JSONResponse({'error': 'Unauthorized'}, status_code=401)

        if not config.ENABLE_ANALYTICS or not state.analytics:
            return JSONResponse({'error': 'Analytics disabled'}, status_code=503)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        metrics = state.analytics.get_date_range_metrics(start_date, end_date)

        return JSONResponse({
            'metrics': metrics,
            'session_stats': state.analytics.get_session_stats(days=days),
            'popular_events': state.analytics.get_popular_events(limit=10, days=days),
            'popular_searches': state.analytics.get_popular_searches(limit=10, days=days),
            'category_popularity': state.analytics.get_category_popularity(days=days),
            'source_performance': state.analytics.get_source_performance(days=days)
        })
