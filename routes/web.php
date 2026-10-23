<?php

use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PythonApiController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return redirect('/dashboard');
});

// Dedicated Clean URLs for Every Navigation Item
Route::get('/dashboard', [DashboardController::class, 'show'])->defaults('view', 'dashboard')->name('dashboard');
Route::get('/ping', [DashboardController::class, 'show'])->defaults('view', 'ping')->name('ping');
Route::get('/monitor', [DashboardController::class, 'show'])->defaults('view', 'monitor')->name('monitor');
Route::get('/alerts', [DashboardController::class, 'show'])->defaults('view', 'alerts')->name('alerts');
Route::get('/records', [DashboardController::class, 'show'])->defaults('view', 'records')->name('records');
Route::get('/reports', [DashboardController::class, 'show'])->defaults('view', 'reports')->name('reports');
Route::get('/ping-records', [DashboardController::class, 'show'])->defaults('view', 'ping-records')->name('ping-records');
Route::get('/ml-insights', [DashboardController::class, 'show'])->defaults('view', 'ml-insights')->name('ml-insights');
Route::get('/settings', [DashboardController::class, 'show'])->defaults('view', 'settings')->name('settings');
Route::get('/about', [DashboardController::class, 'show'])->defaults('view', 'about')->name('about');

// Reverse-proxy all /api/* requests to Python monitoring backend (port 5000)
Route::any('/api/{path}', [PythonApiController::class, 'forward'])->where('path', '.*');
