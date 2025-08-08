import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // Legacy path aliases → Next.js routes for direct navigation/bookmarks
      { source: "/admin_dashboard", destination: "/admin" },
      { source: "/cre_dashboard", destination: "/cre" },
      { source: "/ps_dashboard", destination: "/ps" },
      { source: "/branch_head_dashboard", destination: "/branch-head" },
      { source: "/rec_dashboard", destination: "/rec" },
      { source: "/add_walkin_lead", destination: "/walkin/add" },
      // API proxies
      {
        source: "/api/:path*",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/:path*`
          : "http://localhost:5000/api/:path*",
      },
      {
        source: "/api/rec_dashboard",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/rec_dashboard`
          : "http://localhost:5000/api/rec_dashboard",
      },
      {
        source: "/api/walkin_call_history/:uid",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/walkin_call_history/:uid`
          : "http://localhost:5000/api/walkin_call_history/:uid",
      },
      {
        source: "/api/add_walkin_lead",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/add_walkin_lead`
          : "http://localhost:5000/api/add_walkin_lead",
      },
      {
        source: "/api/update_walkin_lead/:id",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/update_walkin_lead/:id`
          : "http://localhost:5000/api/update_walkin_lead/:id",
      },
      {
        source: "/api/branch_head_dashboard_data",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/branch_head_dashboard_data`
          : "http://localhost:5000/api/branch_head_dashboard_data",
      },
      {
        source: "/api/hot_duplicate_leads",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/hot_duplicate_leads`
          : "http://localhost:5000/api/hot_duplicate_leads",
      },
      {
        source: "/delete_duplicate_lead",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/delete_duplicate_lead`
          : "http://localhost:5000/delete_duplicate_lead",
      },
      {
        source: "/api/transfer_options",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/transfer_options`
          : "http://localhost:5000/api/transfer_options",
      },
      {
        source: "/api/transfer_cre_lead",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/transfer_cre_lead`
          : "http://localhost:5000/api/transfer_cre_lead",
      },
      {
        source: "/api/transfer_ps_lead",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/transfer_ps_lead`
          : "http://localhost:5000/api/transfer_ps_lead",
      },
      {
        source: "/api/change_password",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/change_password`
          : "http://localhost:5000/api/change_password",
      },
      {
        source: "/api/lead/:uid",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/lead/:uid`
          : "http://localhost:5000/api/lead/:uid",
      },
      {
        source: "/api/ps_lead/:uid",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/ps_lead/:uid`
          : "http://localhost:5000/api/ps_lead/:uid",
      },
      {
        source: "/api/add_cre",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/add_cre`
          : "http://localhost:5000/api/add_cre",
      },
      {
        source: "/api/add_ps",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/add_ps`
          : "http://localhost:5000/api/add_ps",
      },
      {
        source: "/api/upload_data",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/upload_data`
          : "http://localhost:5000/api/upload_data",
      },
      {
        source: "/api/analytics",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/analytics`
          : "http://localhost:5000/api/analytics",
      },
      {
        source: "/api/cre_users",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/cre_users`
          : "http://localhost:5000/api/cre_users",
      },
      {
        source: "/api/ps_users",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/ps_users`
          : "http://localhost:5000/api/ps_users",
      },
      {
        source: "/api/leads_admin",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/leads_admin`
          : "http://localhost:5000/api/leads_admin",
      },
      {
        source: "/api/delete_leads",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/delete_leads`
          : "http://localhost:5000/api/delete_leads",
      },
      {
        source: "/dashboard_leads_optimized",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/dashboard_leads_optimized`
          : "http://localhost:5000/dashboard_leads_optimized",
      },
      {
        source: "/api/admin_dashboard_summary",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/admin_dashboard_summary`
          : "http://localhost:5000/api/admin_dashboard_summary",
      },
      {
        source: "/api/session",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/api/session`
          : "http://localhost:5000/api/session",
      },
      {
        source: "/unified_login_json",
        destination: process.env.NEXT_PUBLIC_API_BASE
          ? `${process.env.NEXT_PUBLIC_API_BASE}/unified_login_json`
          : "http://localhost:5000/unified_login_json",
      },
    ];
  },
};

export default nextConfig;
