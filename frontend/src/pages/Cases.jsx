import { useState, useEffect } from 'react';
import { Table, Button, Select, Space, Tag, message, Modal, Form, Input } from 'antd';
import { EyeOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { casesAPI } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;

const statusColor = { 'Pending': 'orange', 'In Progress': 'blue', 'Resolved': 'green', 'Closed': 'default' };

function Cases() {
  const [loading, setLoading] = useState(false);
  const [cases, setCases] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState(null);
  const [channel, setChannel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [statusVisible, setStatusVisible] = useState(false);
  const [selected, setSelected] = useState(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const fetch = () => {
    setLoading(true);
    casesAPI.getAll(page, 20, status, channel)
      .then(r => { setCases(r.data.cases || []); setTotal(r.data.total || 0); })
      .catch(() => message.error('加载案件失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetch(); }, [page, status, channel]);

  const viewDetail = (id) => casesAPI.getOne(id).then(r => { setDetail(r.data); setDetailVisible(true); }).catch(() => message.error('操作失败'));
  const openStatus = (rec) => { setSelected(rec); form.setFieldsValue({ new_status: rec.status, admin_notes: '' }); setStatusVisible(true); };
  const submitStatus = async (v) => {
    try { await casesAPI.updateStatus(selected.case_no, v.new_status, v.admin_notes); message.success('状态已更新'); setStatusVisible(false); fetch(); }
    catch { message.error('Failed'); }
  };

  const cols = [
    { title: '案件编号', dataIndex: 'case_no', key: 'case_no' },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: v => <Tag color="blue">{v}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', render: v => <Tag color={statusColor[v] || 'default'}>{v}</Tag> },
    { title: '平台', dataIndex: 'platform', key: 'platform' },
    { title: '涉案金额', dataIndex: 'amount', key: 'amount', render: v => v ? `$${v}` : '-' },
    { title: '提交时间', dataIndex: 'created_at', key: 'created_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', render: (_, r) => (
      <Space>
        <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/cases/${r.case_no}`)}>详情</Button>
        <Button type="link" icon={<EditOutlined />} onClick={() => openStatus(r)}>改状态</Button>
      </Space>
    )},
  ];

  return (
    <div>
      <div className="page-header"><h1 className="page-title">案件管理</h1></div>
      <div className="content-wrapper">
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Select placeholder="按状态筛选" style={{ width: 180 }} allowClear onChange={setStatus}>
              <Option value="Pending">Pending</Option>
              <Option value="In Progress">In Progress</Option>
              <Option value="Resolved">Resolved</Option>
              <Option value="Closed">Closed</Option>
            </Select>
            <Select placeholder="按渠道筛选" style={{ width: 180 }} allowClear onChange={setChannel}>
              <Option value="telegram">Telegram</Option>
              <Option value="whatsapp">WhatsApp</Option>
              <Option value="web">Web</Option>
            </Select>
            <Button icon={<ReloadOutlined />} onClick={fetch}>刷新</Button>
          </Space>
        </div>
        <Table dataSource={cases} columns={cols} loading={loading} rowKey="case_no"
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: t => `共 ${t} 条` }} />
      </div>

      <Modal title="案件摘要" open={detailVisible} onCancel={() => setDetailVisible(false)} footer={null} width={600}>
        {detail && (
          <div style={{ lineHeight: 2 }}>
            <p><b>案件编号：</b> {detail.case_no}</p>
            <p><b>渠道：</b> {detail.channel}</p>
            <p><b>状态：</b> <Tag color={statusColor[detail.status] || 'default'}>{detail.status}</Tag></p>
            <p><b>平台：</b> {detail.platform}</p>
            <p><b>涉案金额：</b> ${detail.amount}</p>
            <p><b>提交时间：</b> {detail.created_at ? new Date(detail.created_at).toLocaleString('zh-CN') : '-'}</p>
          </div>
        )}
      </Modal>

      <Modal title="更新案件状态" open={statusVisible} onCancel={() => setStatusVisible(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={submitStatus}>
          <Form.Item label="新状态" name="new_status" rules={[{ required: true, message: '请选择状态' }]}>
            <Select>
              <Option value="Pending">Pending</Option>
              <Option value="In Progress">In Progress</Option>
              <Option value="Under Review">Under Review</Option>
              <Option value="Resolved">Resolved</Option>
              <Option value="Closed">Closed</Option>
            </Select>
          </Form.Item>
          <Form.Item label="管理备注" name="admin_notes">
            <TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default Cases;
