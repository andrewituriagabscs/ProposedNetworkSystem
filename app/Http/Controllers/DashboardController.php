<?php

namespace App\Http\Controllers;

use Illuminate\View\View;

class DashboardController extends Controller
{
    /**
     * Display the monitoring dashboard with the specified view panel active.
     */
    public function show(string $view = 'dashboard'): View
    {
        $viewMap = [
            'dashboard' => 'dashboard',
            'ping' => 'monitor',
            'monitor' => 'monitor',
            'alerts' => 'alerts',
            'records' => 'reports',
            'reports' => 'reports',
            'ping-records' => 'reports',
            'ml-insights' => 'ml-insights',
            'settings' => 'settings',
            'about' => 'about',
        ];

        $activeView = $viewMap[$view] ?? 'dashboard';

        return view('dashboard', [
            'activeView' => $activeView,
        ]);
    }
}
