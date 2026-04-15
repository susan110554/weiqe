import { useNavigate, useLocation } from 'react-router-dom';

// 配色方案
const colors = {
  skyBlue: '#0284C7',
  skyBlueLight: '#E0F2FE',
  skyBlueDark: '#0369A1',
  grayText: '#1E293B',
  grayMedium: '#64748B',
  grayLight: '#F1F5F9',
  border: '#E2E8F0',
  white: '#FFFFFF'
};

function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();

  // 菜单分组配置（无图标）
  const menuGroups = [
    {
      title: 'MAIN',
      items: [
        { key: '/dashboard', label: '概览' },
        { key: '/cases', label: '案件管理' },
        { key: '/users', label: '用户管理' },
        { key: '/agents', label: '探员管理' },
      ]
    },
    {
      title: 'FINANCE',
      items: [
        { key: '/fee-console', label: '费用设置' },
        { key: '/broadcasts', label: '广播管理' },
      ]
    },
    {
      title: 'CONTENT',
      items: [
        { key: '/templates', label: '消息模板' },
        { key: '/pdf-templates', label: 'PDF模板' },
        { key: '/messages', label: '消息日志' },
      ]
    },
    {
      title: 'SECURITY',
      items: [
        { key: '/blacklist', label: '黑名单' },
        { key: '/admins', label: '管理员' },
        { key: '/audit-logs', label: '审计日志' },
        { key: '/system-settings', label: '系统设置' },
      ]
    }
  ];

  const isActive = (key) => location.pathname === key || location.pathname.startsWith(key + '/');

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* 左侧导航栏 */}
      <aside
        style={{
          width: '260px',
          backgroundColor: colors.white,
          borderRight: `1px solid ${colors.border}`,
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100
        }}
      >
        {/* 顶部品牌区 */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: `1px solid ${colors.border}`,
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <span
            style={{
              color: colors.skyBlue,
              fontSize: '18px',
              fontWeight: 600,
              letterSpacing: '-0.5px'
            }}
          >
            CIVICEYE 控制台
          </span>
        </div>

        {/* 菜单区域 */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '16px 0' }}>
          {menuGroups.map((group, groupIndex) => (
            <div key={groupIndex} style={{ marginBottom: '8px' }}>
              {/* 分组标题 */}
              <div
                style={{
                  padding: '12px 24px 4px',
                  color: colors.grayMedium,
                  fontSize: '12px',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}
              >
                {group.title}
              </div>
              {/* 菜单项 */}
              {group.items.map((item) => {
                const active = isActive(item.key);
                return (
                  <a
                    key={item.key}
                    href={item.key}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(item.key);
                    }}
                    style={{
                      display: 'block',
                      padding: '8px 16px',
                      margin: '2px 16px',
                      borderRadius: '6px',
                      color: active ? colors.skyBlue : colors.grayText,
                      fontSize: '14px',
                      fontWeight: active ? 500 : 400,
                      textDecoration: 'none',
                      backgroundColor: active ? colors.skyBlueLight : 'transparent',
                      borderLeft: active ? `3px solid ${colors.skyBlue}` : '3px solid transparent',
                      transition: 'all 0.2s ease',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        e.target.style.backgroundColor = colors.grayLight;
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        e.target.style.backgroundColor = 'transparent';
                      }
                    }}
                  >
                    {item.label}
                  </a>
                );
              })}
            </div>
          ))}
        </nav>

        {/* 底栏用户区 */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: `1px solid ${colors.border}`,
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}
        >
          <span style={{ fontSize: '13px', color: colors.grayText, fontWeight: 500 }}>
            admin@civiceye
          </span>
          <button
            onClick={handleLogout}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: colors.skyBlue,
              fontSize: '13px',
              cursor: 'pointer',
              textAlign: 'left',
              textDecoration: 'none'
            }}
            onMouseEnter={(e) => {
              e.target.style.textDecoration = 'underline';
            }}
            onMouseLeave={(e) => {
              e.target.style.textDecoration = 'none';
            }}
          >
            退出
          </button>
        </div>
      </aside>

      {/* 主内容区 */}
      <main style={{ marginLeft: '260px', flex: 1, backgroundColor: colors.grayLight, minHeight: '100vh' }}>
        {/* 顶部栏 */}
        <header
          style={{
            backgroundColor: colors.white,
            borderBottom: `1px solid ${colors.border}`,
            padding: '16px 32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 600, color: colors.grayText }}>
            {menuGroups
              .flatMap(g => g.items)
              .find(item => isActive(item.key))?.label || '控制台'}
          </h1>
          <div style={{ fontSize: '14px', color: colors.grayMedium }}>
            CIVICEYE 案件管理系统
          </div>
        </header>

        {/* 页面内容 */}
        <div style={{ padding: '24px 32px' }}>
          {children}
        </div>
      </main>
    </div>
  );
}

export default Layout;
