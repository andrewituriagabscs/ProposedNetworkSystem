<?php

namespace Tests\Feature;

use Tests\TestCase;

class NavigationRoutesTest extends TestCase
{
    public function test_root_redirects_to_dashboard(): void
    {
        $response = $this->get('/');
        $response->assertRedirect('/dashboard');
    }

    public function test_dashboard_route_loads_with_dashboard_panel_active(): void
    {
        $response = $this->get('/dashboard');
        $response->assertStatus(200);
        $response->assertViewHas('activeView', 'dashboard');
        $response->assertSee('data-panel="dashboard"', false);
        $response->assertSee('href="/dashboard"', false);
    }

    public function test_ping_and_monitor_routes_load_with_monitor_panel_active(): void
    {
        foreach (['/ping', '/monitor'] as $url) {
            $response = $this->get($url);
            $response->assertStatus(200);
            $response->assertViewHas('activeView', 'monitor');
            $response->assertSee('data-panel="monitor"', false);
            $response->assertSee('href="/ping"', false);
        }
    }

    public function test_alerts_route_loads_with_alerts_panel_active(): void
    {
        $response = $this->get('/alerts');
        $response->assertStatus(200);
        $response->assertViewHas('activeView', 'alerts');
        $response->assertSee('data-panel="alerts"', false);
        $response->assertSee('href="/alerts"', false);
    }

    public function test_records_routes_load_with_reports_panel_active(): void
    {
        foreach (['/records', '/reports', '/ping-records'] as $url) {
            $response = $this->get($url);
            $response->assertStatus(200);
            $response->assertViewHas('activeView', 'reports');
            $response->assertSee('data-panel="reports"', false);
            $response->assertSee('href="/records"', false);
        }
    }

    public function test_ml_insights_route_loads_with_ml_insights_panel_active(): void
    {
        $response = $this->get('/ml-insights');
        $response->assertStatus(200);
        $response->assertViewHas('activeView', 'ml-insights');
        $response->assertSee('data-panel="ml-insights"', false);
        $response->assertSee('href="/ml-insights"', false);
        $response->assertSee('id="ml-unreachable-rows"', false);
        $response->assertSee('id="ml-performance-rows"', false);
        $response->assertSee('Spot 1: Critical Outages', false);
        $response->assertSee('Spot 2: Performance Anomalies', false);
    }

    public function test_settings_and_about_routes_load(): void
    {
        $response = $this->get('/settings');
        $response->assertStatus(200);
        $response->assertViewHas('activeView', 'settings');

        $response = $this->get('/about');
        $response->assertStatus(200);
        $response->assertViewHas('activeView', 'about');
    }

    public function test_page_contains_clean_client_side_router_logic(): void
    {
        $response = $this->get('/alerts');
        $response->assertStatus(200);
        $content = $response->getContent();

        $this->assertStringContainsString('history.pushState({ view: viewName }, \'\', targetUrl)', $content);
        $this->assertStringContainsString("window.addEventListener('popstate'", $content);
        $this->assertStringContainsString("const viewUrlMap =", $content);
        $this->assertStringContainsString("const urlViewMap =", $content);
        $this->assertStringContainsString("function switchView(viewName", $content);
    }
}
