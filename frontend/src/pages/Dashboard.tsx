import React from 'react';
import { useAuth } from '../contexts/AuthContext';

const Dashboard: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="bg-white overflow-hidden shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Welcome back, {user?.username}! ⚽
          </h1>
          <p className="text-gray-600">
            Ready to optimize your FPL squad with AI-powered insights?
          </p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-2xl">📊</span>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Current Gameweek
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">GW 1</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-2xl">🏆</span>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Squad Value
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">£100.0M</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-2xl">⭐</span>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Predicted Points
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">65.2</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-2">
        {/* Squad Builder Card */}
        <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow cursor-pointer">
          <div className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-4xl">⚽</span>
              </div>
              <div className="ml-6 flex-1">
                <h3 className="text-lg font-medium text-gray-900">Squad Builder</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Build and optimize your squad using AI predictions and mathematical optimization
                </p>
                <div className="mt-4">
                  <a
                    href="/wildcard"
                    className="inline-flex items-center text-sm font-medium text-fpl-purple hover:text-purple-800"
                  >
                    Wildcard Builder
                    <span className="ml-1">→</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Transfer Planner Card */}
        <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow cursor-pointer">
          <div className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-4xl">🔄</span>
              </div>
              <div className="ml-6 flex-1">
                <h3 className="text-lg font-medium text-gray-900">Transfer Planner</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Plan your transfers across multiple gameweeks with chip strategy optimization
                </p>
                <div className="mt-4">
                  <a
                    href="/transfer-planner"
                    className="inline-flex items-center text-sm font-medium text-fpl-purple hover:text-purple-800"
                  >
                    Plan Transfers
                    <span className="ml-1">→</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Players Card */}
        <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow cursor-pointer">
          <div className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-4xl">👤</span>
              </div>
              <div className="ml-6 flex-1">
                <h3 className="text-lg font-medium text-gray-900">Player Analysis</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Explore detailed player statistics, predictions, and performance analytics
                </p>
                <div className="mt-4">
                  <a
                    href="/players"
                    className="inline-flex items-center text-sm font-medium text-fpl-purple hover:text-purple-800"
                  >
                    Analyze Players
                    <span className="ml-1">→</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Analytics Card */}
        <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow cursor-pointer">
          <div className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-4xl">📈</span>
              </div>
              <div className="ml-6 flex-1">
                <h3 className="text-lg font-medium text-gray-900">Performance Analytics</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Track your performance, analyze trends, and compare with other managers
                </p>
                <div className="mt-4">
                  <a
                    href="/analytics"
                    className="inline-flex items-center text-sm font-medium text-fpl-purple hover:text-purple-800"
                  >
                    View Analytics
                    <span className="ml-1">→</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900">
            Recent Activity
          </h3>
        </div>
        <div className="px-4 py-5 sm:p-6">
          <div className="text-center py-8">
            <span className="text-4xl">🚀</span>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No activity yet</h3>
            <p className="mt-1 text-sm text-gray-500">
              Get started by building your first optimized squad!
            </p>
            <div className="mt-6">
              <a
                href="/wildcard"
                className="btn-primary"
              >
                Start Wildcard
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;