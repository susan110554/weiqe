import { useState, useEffect } from 'react';
import { Table, Button, Tag, message, Modal, Form, Input, InputNumber, Switch, Select, Space, Card, Row, Col } from 'antd';
import { EditOutlined, ReloadOutlined } from '@ant-design/icons';
import { feeAPI } from '../services/api';

const { Option } = Select;

const CRYPTO_NETWORKS = [
  { label: 'USDT (TRC-20)', value: 'USDT_TRC20' },
  { label: 'USDT (ERC-20)', value: 'USDT_ERC20' },
  { label: 'USDT (BEP-20)', value: 'USDT_BEP20' },
  { label: 'ETH (ERC-20)', value: 'ETH_ERC20' },
  { label: 'BTC (Bitcoin)', value: 'BTC_MAINNET' },
];

function FeeConsole() {
  const [fees, setFees] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();

  const fetch = () => {
    setLoading(true);
    feeAPI.getAll()
      .then(r => setFees(r.data.fees || []))
      .catch(() => message.error('加载费用配置失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, []);

  const handleEdit = (rec) => {
    setEditing(rec);
    form.setFieldsValue(rec);
    setModalOpen(true);
  };

  const handleSubmit = async (values) => {
    try {
      await feeAPI.update(editing.id, values);
      message.success('费用已更新');
      setModalOpen(false);
      fetch();
    } catch { message.error('操作失败'); }
  };

  const cols = [
    { title: '费用类型', dataIndex: 'fee_type', key: 'fee_type', render: v => <Tag color="blue">{v}</Tag> },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (v, r) => `${v} ${r.currency || 'USD'}` },
    { title: '阶段', dataIndex: 'phase', key: 'phase', render: v => v ? <Tag color="orange">{v}</Tag> : '-' },
    { title: '是否启用', dataIndex: 'enabled', key: 'enabled', render: v => <Tag color={v ? 'green' : 'red'}>{v ? '是' : '否'}</Tag> },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(r)}>编辑</Button>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">费用控制台</h1></div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {[
          { label: 'P5 身份验证', color: '#1890ff' },
          { label: 'P10 制裁筛查', color: '#fa8c16' },
          { label: 'P11 协议转换', color: '#722ed1' },
          { label: 'P12 最终授权', color: '#52c41a' },
        ].map((item, i) => (
          <Col xs={24} sm={12} md={6} key={i}>
            <Card style={{ borderLeft: `4px solid ${item.color}` }}>
              <div style={{ fontSize: 12, color: '#999' }}>{item.label}</div>
              <div style={{ fontSize: 20, fontWeight: 'bold', color: item.color }}>
                {fees.find(f => f.fee_type?.includes(item.label.split(' ')[0]))?.amount || '—'} 美元
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Card title="收款地址" style={{ marginBottom: 16 }}>
        <Table
          dataSource={CRYPTO_NETWORKS.map(n => ({ ...n, key: n.value }))}
          columns={[
            { title: '网络', dataIndex: 'label', key: 'label', render: v => <Tag color="blue">{v}</Tag> },
            { title: '地址', key: 'address', render: (_, r) => fees.find(f => f.network === r.value)?.crypto_address || <span style={{ color: '#999' }}>未配置</span> },
            { title: '操作', key: 'actions', render: (_, r) => {
              const fee = fees.find(f => f.network === r.value);
              return fee ? <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(fee)}>编辑</Button> : null;
            }},
          ]}
          pagination={false}
          size="small"
        />
      </Card>

      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
        </div>
        <Table dataSource={fees} columns={cols} loading={loading} rowKey="id" pagination={{ pageSize: 20 }} />
      </div>

      <Modal title="编辑费用配置" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item label="费用类型" name="fee_type" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="金额" name="amount" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={0} /></Form.Item>
          <Form.Item label="货币" name="currency" initialValue="USD">
            <Select>
              <Option value="USD">美元</Option>
              <Option value="USDT">泰达币</Option>
              <Option value="ETH">以太坊</Option>
              <Option value="BTC">比特币</Option>
            </Select>
          </Form.Item>
          <Form.Item label="支付网络" name="network">
            <Select allowClear>
              {CRYPTO_NETWORKS.map(n => <Option key={n.value} value={n.value}>{n.label}</Option>)}
            </Select>
          </Form.Item>
          <Form.Item label="加密货币地址" name="crypto_address"><Input placeholder="0x... 或 T..." /></Form.Item>
          <Form.Item label="是否启用" name="enabled" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default FeeConsole;
