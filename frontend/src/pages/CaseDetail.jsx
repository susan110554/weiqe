import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Button, Tag, Descriptions, Table, Form, Input, Select,
  Modal, message, Spin, Space, Divider, Row, Col, InputNumber, Tabs,
  Alert, Upload, Popconfirm, Badge, Empty, Switch, DatePicker, TimePicker
} from 'antd';
import {
  ArrowLeftOutlined, SendOutlined, ExclamationCircleOutlined, FilePdfOutlined,
  PlusOutlined, DeleteOutlined, UploadOutlined, CheckCircleOutlined, CloseCircleOutlined,
  EyeOutlined, RocketOutlined, BellOutlined, UserOutlined, CalendarOutlined,
  EditOutlined, ClockCircleOutlined, PlayCircleOutlined, PauseCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { casesAPI, casePhaseAPI, agentsAPI, pushTaskAPI } from '../services/api';
import dayjs from 'dayjs';

const { TextArea } = Input;
const { Option } = Select;
const { confirm } = Modal;
const { TabPane } = Tabs;

const PHASES = ['P1','P2','P3','P4','P5','P6','P7','P8','P9','P10','P11','P12'];
const PHASE_LABELS = {
  P1:'案件提交', P2:'初步验证', P3:'审核中', P4:'转介评估',
  P5:'身份验证', P6:'初步审查', P7:'资产追踪', P8:'法律文书',
  P9:'资金分配', P10:'制裁筛查', P11:'协议转换', P12:'最终授权'
};
const PHASE_NEXT = { P1:'P2',P2:'P3',P3:'P4',P4:'P5',P5:'P6',P6:'P7',P7:'P8',P8:'P9',P9:'P10',P10:'P11',P11:'P12' };

// 配色方案
const colors = {
  skyBlue: '#0284C7',
  skyBlueLight: '#E0F2FE',
  skyBlueDark: '#0369A1',
  grayText: '#1E293B',
  grayMedium: '#64748B',
  grayLight: '#F1F5F9',
  border: '#E2E8F0',
  white: '#FFFFFF',
  green: '#10B981',
  red: '#EF4444',
  orange: '#F97316'
};

// ── P1-P12 可点击进度条组件 ─────────────────────────────────────────
function PhaseProgressBar({ currentPhase, actualPhase, onSelect, caseStatus }) {
  const currentIndex = PHASES.indexOf(currentPhase);
  const actualIndex = PHASES.indexOf(actualPhase);

  return (
    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', padding: '8px 0' }}>
      {PHASES.map((phase, index) => {
        const isCurrent = index === currentIndex;
        const isActual = index === actualIndex;
        const isPast = index < actualIndex;
        const isFuture = index > actualIndex;

        return (
          <div
            key={phase}
            onClick={() => onSelect(phase)}
            style={{
              minWidth: 70,
              padding: '12px 8px',
              borderRadius: 8,
              cursor: 'pointer',
              textAlign: 'center',
              backgroundColor: isCurrent ? colors.skyBlueLight : colors.white,
              border: isCurrent ? `2px solid ${colors.skyBlue}` : `1px solid ${colors.border}`,
              boxShadow: isCurrent ? '0 2px 8px rgba(2,132,199,0.2)' : 'none',
              transition: 'all 0.2s ease',
              position: 'relative'
            }}
            onMouseEnter={(e) => {
              if (!isCurrent) {
                e.currentTarget.style.backgroundColor = colors.grayLight;
                e.currentTarget.style.borderColor = colors.skyBlue;
              }
            }}
            onMouseLeave={(e) => {
              if (!isCurrent) {
                e.currentTarget.style.backgroundColor = colors.white;
                e.currentTarget.style.borderColor = colors.border;
              }
            }}
          >
            {/* 阶段编号 */}
            <div
              style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 6px',
                fontSize: 12,
                fontWeight: 600,
                backgroundColor: isActual ? colors.skyBlue : isPast ? colors.green : colors.grayLight,
                color: isActual || isPast ? colors.white : colors.grayMedium,
                border: isActual ? `2px solid ${colors.skyBlueDark}` : 'none'
              }}
            >
              {index + 1}
            </div>

            {/* 阶段标识 */}
            <div style={{ fontSize: 12, fontWeight: isCurrent ? 600 : 500, color: isCurrent ? colors.skyBlue : colors.grayText }}>
              {phase}
            </div>

            {/* 阶段名称 - 仅显示前两字 */}
            <div style={{ fontSize: 10, color: colors.grayMedium, marginTop: 2 }}>
              {PHASE_LABELS[phase].slice(0, 3)}
            </div>

            {/* "当前阶段" 角标 */}
            {isActual && (
              <Badge
                count="当前"
                style={{
                  position: 'absolute',
                  top: -8,
                  right: -4,
                  backgroundColor: colors.orange,
                  fontSize: 9,
                  padding: '0 4px'
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── 阶段操作面板 ─────────────────────────────────────────
function PhaseOperationPanel({ caseData, selectedPhase, actualPhase, onAdvance, agents = [] }) {
  const [form] = Form.useForm();
  const [overrides, setOverrides] = useState(caseData?.case_cmp_overrides || {});
  const [showPreview, setShowPreview] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [loading, setLoading] = useState(false);

  const isActualPhase = selectedPhase === actualPhase;
  const nextPhase = PHASE_NEXT[selectedPhase];

  const saveOverrides = async () => {
    try {
      setLoading(true);
      await casePhaseAPI.updateOverrides(caseData.case_no, overrides);
      message.success('配置已保存');
    } catch { message.error('保存失败'); }
    finally { setLoading(false); }
  };

  const handleAdvance = (customPhase, customNotes) => {
    if (!isActualPhase) {
      message.warning('只能在实际所处阶段推进案件');
      return;
    }
    const target = customPhase || nextPhase;
    confirm({
      title: `确认推进至 ${target}?`,
      icon: <ExclamationCircleOutlined />,
      onOk: async () => {
        try {
          const vals = await form.validateFields().catch(() => ({ notes: '' }));
          await onAdvance({ new_phase: target, notes: customNotes || vals.notes || '' });
        } catch (e) {
          message.error(e?.response?.data?.detail || '推进失败');
        }
      }
    });
  };

  const feeKey = `${selectedPhase.toLowerCase()}Items`;
  const feeItems = overrides[feeKey] || [];
  const updateFeeItems = (items) => setOverrides(p => ({ ...p, [feeKey]: items }));

  // 各阶段渲染内容
  const renderPhaseContent = () => {
    const commonNotes = (
      <>
        <Divider dashed />
        <Form.Item label="阶段备注" name="notes">
          <TextArea rows={2} placeholder="操作备注（可选）" />
        </Form.Item>
      </>
    );

    switch (selectedPhase) {
      case 'P1':
        return (
          <>
            <Alert message="P1 案件提交" description="等待用户确认提交，确认接收后案件进入初步验证阶段。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="涉案金额">{caseData.amount ? `${caseData.amount} ${caseData.coin}` : '未填写'}</Descriptions.Item>
              <Descriptions.Item label="区块链">{caseData.chain_type || '未填写'}</Descriptions.Item>
              <Descriptions.Item label="平台">{caseData.platform || '未填写'}</Descriptions.Item>
            </Descriptions>
            {isActualPhase && (
              <>
                <Divider />
                <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => handleAdvance()}>
                  确认接收 → P2
                </Button>
              </>
            )}
            {commonNotes}
          </>
        );

      case 'P2':
        return (
          <>
            <Alert message="P2 初步验证" description="验证地址格式和交易哈希有效性，可手动覆盖验证结果。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="验证结果">
              <Select value={overrides.verifyResult} onChange={v => setOverrides(p => ({ ...p, verifyResult: v }))}>
                <Option value="pass">✅ 通过</Option>
                <Option value="fail">❌ 失败</Option>
                <Option value="manual">⚠️ 手动覆盖</Option>
              </Select>
            </Form.Item>
            <Form.Item label="验证备注">
              <TextArea rows={2} value={overrides.verifyNote} onChange={e => setOverrides(p => ({ ...p, verifyNote: e.target.value }))} />
            </Form.Item>
            <Space>
              <Button onClick={saveOverrides} loading={loading}>保存验证结果</Button>
              {isActualPhase && overrides.verifyResult === 'pass' && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  验证通过 → P3
                </Button>
              )}
            </Space>
            {commonNotes}
          </>
        );

      case 'P3':
        return (
          <>
            <Alert message="P3 审核中" description="指派探员并开启联络通道。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="指派探员">
              {agents.length > 0 ? (
                <Select value={overrides.agentCode} onChange={v => setOverrides(p => ({ ...p, agentCode: v }))} placeholder="选择探员" showSearch>
                  {agents.map(a => <Option key={a.agent_code} value={a.agent_code}>{a.agent_code} - {a.name || '—'}</Option>)}
                </Select>
              ) : (
                <Input value={overrides.agentCode} placeholder="如: SA-7821" onChange={e => setOverrides(p => ({ ...p, agentCode: e.target.value }))} />
              )}
            </Form.Item>
            <Space style={{ marginBottom: 12 }}>
              <Button onClick={saveOverrides} loading={loading}>保存探员</Button>
              <Button type="dashed" onClick={() => { setOverrides(p => ({ ...p, contactChannelOpen: true })); message.success('联络通道已开启'); }}>
                开启联络通道
              </Button>
              {overrides.contactChannelOpen && <Tag color="green">联络通道已开启</Tag>}
            </Space>
            {isActualPhase && overrides.agentCode && (
              <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                指派完成 → P4
              </Button>
            )}
            {commonNotes}
          </>
        );

      case 'P4':
        return (
          <>
            <Alert message="P4 转介评估" description="评估是否需要转介其他机构处理。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="是否转介">
              <Select value={overrides.referral} onChange={v => setOverrides(p => ({ ...p, referral: v }))}>
                <Option value="no">不转介</Option>
                <Option value="yes">转介其他机构</Option>
              </Select>
            </Form.Item>
            {overrides.referral === 'yes' && (
              <Form.Item label="转介机构">
                <Input value={overrides.referralOrg} onChange={e => setOverrides(p => ({ ...p, referralOrg: e.target.value }))} placeholder="机构名称" />
              </Form.Item>
            )}
            <Form.Item label="内部评估意见">
              <TextArea rows={3} value={overrides.assessment} onChange={e => setOverrides(p => ({ ...p, assessment: e.target.value }))} />
            </Form.Item>
            <Space>
              <Button onClick={saveOverrides} loading={loading}>保存评估</Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  评估完成 → P5
                </Button>
              )}
            </Space>
            {commonNotes}
          </>
        );

      case 'P5':
        return (
          <>
            <Alert message="P5 身份验证" description="审核用户上传的身份证件。" type="warning" showIcon style={{ marginBottom: 16 }} />
            {overrides.idDocUrl && (
              <div style={{ marginBottom: 16 }}>
                <img src={overrides.idDocUrl} alt="证件" style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #eee' }} />
              </div>
            )}
            <Space style={{ marginBottom: 12 }}>
              <Popconfirm title="确认审核通过?" onConfirm={() => { setOverrides(p => ({ ...p, idVerified: 'approved' })); saveOverrides().then(() => handleAdvance()); }}>
                <Button type="primary" icon={<CheckCircleOutlined />}>审核通过 → P6</Button>
              </Popconfirm>
              <Button danger icon={<CloseCircleOutlined />} onClick={() => {
                Modal.confirm({
                  title: '驳回身份验证',
                  content: <TextArea rows={3} placeholder="请填写驳回原因" onChange={e => setRejectReason(e.target.value)} />,
                  onOk: () => { setOverrides(p => ({ ...p, idVerified: 'rejected', rejectReason })); saveOverrides(); message.warning('已驳回'); }
                });
              }}>驳回</Button>
            </Space>
            {overrides.idVerified && (
              <Tag color={overrides.idVerified === 'approved' ? 'green' : 'red'} style={{ marginBottom: 12 }}>
                {overrides.idVerified === 'approved' ? '✅ 已通过' : `❌ 已驳回: ${overrides.rejectReason || ''}`}
              </Tag>
            )}
            {commonNotes}
          </>
        );

      case 'P6':
        return (
          <>
            <Alert message="P6 初步审查" description="进行初步审查，补充调查文件。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="审查意见（内部）">
              <TextArea rows={4} value={overrides.reviewNote} onChange={e => setOverrides(p => ({ ...p, reviewNote: e.target.value }))} />
            </Form.Item>
            <Form.Item label="补充调查文件">
              <Upload beforeUpload={() => false} accept=".pdf,.jpg,.png">
                <Button icon={<UploadOutlined />}>上传文件</Button>
              </Upload>
            </Form.Item>
            <Space>
              <Button onClick={saveOverrides} loading={loading}>保存审查意见</Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  审查完成 → P7
                </Button>
              )}
            </Space>
            {commonNotes}
          </>
        );

      case 'P7':
        return (
          <>
            <Alert message="P7 资产追踪" description="进行资产追踪分析。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Descriptions bordered size="small" column={1} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="收款钱包地址">{caseData.wallet_addr || '未提供'}</Descriptions.Item>
              <Descriptions.Item label="涉案金额">{caseData.amount ? `${caseData.amount} ${caseData.coin}` : '-'}</Descriptions.Item>
            </Descriptions>
            <Form.Item label="RAD-02 风险评分">
              <InputNumber min={0} max={100} value={overrides.radScore} onChange={v => setOverrides(p => ({ ...p, radScore: v }))} />
            </Form.Item>
            <Form.Item label="追踪备注">
              <TextArea rows={3} value={overrides.trackNote} onChange={e => setOverrides(p => ({ ...p, trackNote: e.target.value }))} />
            </Form.Item>
            <Space>
              <Button onClick={saveOverrides} loading={loading}>保存追踪结果</Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  追踪完成 → P8
                </Button>
              )}
            </Space>
            {commonNotes}
          </>
        );

      case 'P8':
        return (
          <>
            <Alert message="P8 法律文书" description="准备法律文书，上传冻结令/扣押令。" type="warning" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="资产返还钱包地址">
              <Input value={overrides.returnWallet || caseData.wallet_addr} onChange={e => setOverrides(p => ({ ...p, returnWallet: e.target.value }))} />
            </Form.Item>
            <Form.Item label="上传法律文件">
              <Upload beforeUpload={() => false} accept=".pdf">
                <Button icon={<FilePdfOutlined />}>上传 PDF</Button>
              </Upload>
            </Form.Item>
            <Space>
              <Button onClick={saveOverrides} loading={loading}>保存</Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  文书准备完成 → P9
                </Button>
              )}
            </Space>
            {commonNotes}
          </>
        );

      case 'P9':
        return (
          <>
            <Alert message="P9 资金分配" description="配置分配金额和费用项目。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="分配金额 (USDT)">
              <InputNumber style={{ width: '100%' }} value={overrides.p9Amount} onChange={v => setOverrides(p => ({ ...p, p9Amount: v }))} />
            </Form.Item>
            <Form.Item label="联邦合约地址 (TRC-20)">
              <Input value={overrides.contractAddress} onChange={e => setOverrides(p => ({ ...p, contractAddress: e.target.value }))} />
            </Form.Item>
            <Form.Item label="费用项目">
              <FeeItemsEditor items={feeItems} onChange={updateFeeItems} />
            </Form.Item>
            <Space style={{ marginBottom: 16 }}>
              <Button onClick={saveOverrides} loading={loading}>💾 保存配置</Button>
              <Button icon={<EyeOutlined />} onClick={() => setShowPreview(p => !p)}>
                {showPreview ? '隐藏预览' : '📱 推送预览'}
              </Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  配置完成 → P10
                </Button>
              )}
            </Space>
            {showPreview && (
              <div style={{ marginBottom: 16 }}>
                <PushPreview phase={selectedPhase} caseNo={caseData.case_no} overrides={overrides} />
              </div>
            )}
            {commonNotes}
          </>
        );

      case 'P10':
        return (
          <>
            <Alert message="P10 制裁筛查" description="进行制裁名单筛查。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="费用项目">
              <FeeItemsEditor items={feeItems} onChange={updateFeeItems} />
            </Form.Item>
            <Space style={{ marginBottom: 16 }}>
              <Button onClick={saveOverrides} loading={loading}>💾 保存配置</Button>
              <Button icon={<EyeOutlined />} onClick={() => setShowPreview(p => !p)}>
                {showPreview ? '隐藏预览' : '📱 推送预览'}
              </Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  筛查完成 → P11
                </Button>
              )}
            </Space>
            {showPreview && (
              <div style={{ marginBottom: 16 }}>
                <PushPreview phase={selectedPhase} caseNo={caseData.case_no} overrides={overrides} />
              </div>
            )}
            {commonNotes}
          </>
        );

      case 'P11':
        return (
          <>
            <Alert message="P11 协议转换" description="协议转换和最终准备。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="费用项目">
              <FeeItemsEditor items={feeItems} onChange={updateFeeItems} />
            </Form.Item>
            <Space style={{ marginBottom: 16 }}>
              <Button onClick={saveOverrides} loading={loading}>💾 保存配置</Button>
              <Button icon={<EyeOutlined />} onClick={() => setShowPreview(p => !p)}>
                {showPreview ? '隐藏预览' : '📱 推送预览'}
              </Button>
              {isActualPhase && (
                <Button type="primary" icon={<RocketOutlined />} onClick={() => handleAdvance()}>
                  转换完成 → P12
                </Button>
              )}
            </Space>
            {showPreview && (
              <div style={{ marginBottom: 16 }}>
                <PushPreview phase={selectedPhase} caseNo={caseData.case_no} overrides={overrides} />
              </div>
            )}
            {commonNotes}
          </>
        );

      case 'P12':
        return (
          <>
            <Alert message="P12 最终授权" description="最终阶段，生成报告并完成结案。" type="success" showIcon style={{ marginBottom: 16 }} />
            <Form.Item label="费用项目">
              <FeeItemsEditor items={feeItems} onChange={updateFeeItems} />
            </Form.Item>
            <Space style={{ marginBottom: 16 }}>
              <Button onClick={saveOverrides} loading={loading}>💾 保存配置</Button>
              <Button icon={<EyeOutlined />} onClick={() => setShowPreview(p => !p)}>
                {showPreview ? '隐藏预览' : '📱 推送预览'}
              </Button>
            </Space>
            {showPreview && (
              <div style={{ marginBottom: 16 }}>
                <PushPreview phase={selectedPhase} caseNo={caseData.case_no} overrides={overrides} />
              </div>
            )}
            <Divider dashed />
            <Space>
              <Button icon={<FilePdfOutlined />} onClick={() => message.info('PDF生成功能待集成')}>生成最终报告 PDF</Button>
              {isActualPhase && (
                <Popconfirm title="确认结案？案件将标记为CLOSED。" onConfirm={() => handleAdvance('CLOSED', '案件已完成结案')}>
                  <Button type="primary" danger>✅ 完成结案</Button>
                </Popconfirm>
              )}
            </Space>
            {commonNotes}
          </>
        );

      default:
        return <Alert message={`${selectedPhase} 阶段操作面板`} type="info" />;
    }
  };

  return (
    <Card
      title={
        <Space>
          <Tag color={isActualPhase ? 'blue' : 'default'} style={{ fontSize: 14 }}>{selectedPhase}</Tag>
          <span>{PHASE_LABELS[selectedPhase]}</span>
          {!isActualPhase && <Tag color="orange">仅查看</Tag>}
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Form form={form} layout="vertical">
        {renderPhaseContent()}
      </Form>
    </Card>
  );
}

// ── 费用项目编辑器 ─────────────────────────────────────────
function FeeItemsEditor({ items = [], onChange }) {
  const add = () => onChange([...items, { name: '', amount: 0 }]);
  const remove = (i) => onChange(items.filter((_, idx) => idx !== i));
  const update = (i, field, val) => {
    const next = items.map((r, idx) => idx === i ? { ...r, [field]: val } : r);
    onChange(next);
  };
  const total = items.reduce((s, r) => s + (Number(r.amount) || 0), 0);

  return (
    <div>
      <Table size="small" pagination={false} rowKey={(_, i) => i}
        dataSource={items}
        columns={[
          { title: '费用名称', dataIndex: 'name', key: 'name', render: (v, _, i) =>
            <Input size="small" value={v} onChange={e => update(i, 'name', e.target.value)} placeholder="如：处理手续费" /> },
          { title: '金额 (USD)', dataIndex: 'amount', key: 'amount', width: 150, render: (v, _, i) =>
            <InputNumber size="small" value={v} min={0} style={{ width: '100%' }} onChange={val => update(i, 'amount', val)} /> },
          { title: '', key: 'del', width: 40, render: (_, __, i) =>
            <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(i)} /> },
        ]}
        footer={() => (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={add}>添加费用项</Button>
            <span style={{ fontWeight: 'bold' }}>合计：<span style={{ color: '#f5222d', fontSize: 16 }}>${total.toFixed(2)}</span></span>
          </div>
        )}
      />
    </div>
  );
}

// ── 推送预览 ─────────────────────────────────────────
function PushPreview({ phase, caseNo, overrides }) {
  const items = overrides[`${phase.toLowerCase()}Items`] || [];
  const total = items.reduce((s, r) => s + (Number(r.amount) || 0), 0);

  return (
    <div style={{ background: '#e3f2fd', borderRadius: 12, padding: 16, maxWidth: 380, fontFamily: 'sans-serif' }}>
      <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>📱 用户将收到的消息预览</div>
      <div style={{ background: '#fff', borderRadius: 8, padding: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.1)' }}>
        <div style={{ fontWeight: 'bold', color: '#0050b3', marginBottom: 8 }}>🔒 FBI IC3 - {phase} 通知</div>
        <div style={{ fontSize: 13, color: '#333', marginBottom: 8 }}>案件编号：<b>{caseNo}</b></div>
        {phase === 'P9' && overrides.contractAddress && (
          <div style={{ fontSize: 12, marginBottom: 8 }}>合约地址：<code style={{ fontSize: 10 }}>{overrides.contractAddress}</code></div>
        )}
        {items.length > 0 && (
          <div style={{ borderTop: '1px solid #eee', paddingTop: 8, marginTop: 8 }}>
            {items.map((it, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span>{it.name}</span><span style={{ color: '#f5222d' }}>${Number(it.amount).toFixed(2)}</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', borderTop: '1px solid #eee', paddingTop: 4, marginTop: 4 }}>
              <span>总计</span><span style={{ color: '#f5222d' }}>${total.toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── 聊天面板 ─────────────────────────────────────────
function ChatPanel({ caseNo }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const bottom = useRef(null);

  const load = () => casePhaseAPI.getMessages(caseNo).then(r => {
    setMsgs(r.data.messages || []);
    setTimeout(() => bottom.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  }).catch(() => {});

  useEffect(() => { load(); }, [caseNo]);

  const send = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      await casePhaseAPI.sendMessage(caseNo, { content: text, sender_type: 'admin' });
      setText('');
      load();
    } catch { message.error('发送失败'); }
    finally { setSending(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 400 }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 12, background: '#f5f5f5', borderRadius: 8, marginBottom: 8 }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ marginBottom: 8, textAlign: m.sender_type === 'admin' ? 'right' : 'left' }}>
            <div style={{ display: 'inline-block', background: m.sender_type === 'admin' ? '#1890ff' : '#fff',
              color: m.sender_type === 'admin' ? '#fff' : '#000', padding: '8px 12px', borderRadius: 12, maxWidth: '75%' }}>
              {m.content}
            </div>
            <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
              {m.sender_type} · {m.sent_at ? new Date(m.sent_at).toLocaleString('zh-CN') : ''}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <Space.Compact style={{ width: '100%' }}>
        <Input value={text} onChange={e => setText(e.target.value)} placeholder="以探员身份发送消息..." onPressEnter={send} />
        <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={send}>发送</Button>
      </Space.Compact>
    </div>
  );
}

// ── 自动推送设置组件 ─────────────────────────────────────────
function AutoPushSettings({ caseData }) {
  const [enabled, setEnabled] = useState(caseData?.auto_push_enabled || false);
  const [schedule, setSchedule] = useState(caseData?.auto_push_schedule || null);
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    try {
      await casePhaseAPI.updateAutoPush(caseData.case_no, { enabled, schedule });
      message.success('自动推送设置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title={<><BellOutlined /> 系统自动推送</>} style={{ marginBottom: 16 }}>
      <Form layout="vertical">
        <Form.Item label="启用自动推送">
          <Switch checked={enabled} onChange={setEnabled} />
        </Form.Item>
        {enabled && (
          <Form.Item label="推送时间">
            <DatePicker
              showTime
              value={schedule ? dayjs(schedule) : null}
              onChange={(date) => setSchedule(date ? date.format('YYYY-MM-DD HH:mm:ss') : null)}
              style={{ width: '100%' }}
              placeholder="选择推送时间"
            />
          </Form.Item>
        )}
        <Button type="primary" onClick={handleSave} loading={loading}>保存设置</Button>
      </Form>
    </Card>
  );
}

// ── 个人案件推送组件 ─────────────────────────────────────────
// 自动推送当前案件的 Case Overview 给单个用户（P1-P12阶段）
function PersonalPush({ caseData }) {
  const [pushData, setPushData] = useState({
    scheduledAt: null,
    immediate: true
  });
  const [loading, setLoading] = useState(false);

  // 构建 Case Overview 显示
  const buildCaseOverview = () => {
    const phase = caseData?.status || 'P1';
    const platform = caseData?.platform || 'N/A';
    const amount = caseData?.amount || 'N/A';
    const coin = caseData?.coin || '';
    const caseNo = caseData?.case_no || 'N/A';
    const createdAt = caseData?.created_at ? caseData.created_at.substring(0, 10) : 'N/A';
    
    return {
      phase,
      platform,
      amount,
      coin,
      caseNo,
      createdAt,
      overviewText: `📋 Case Overview - ${caseNo}
━━━━━━━━━━━━━━━━━━━━━
📊 当前阶段: ${phase}
💰 涉案金额: ${amount} ${coin}
📱 平台: ${platform}
📅 提交时间: ${createdAt}
━━━━━━━━━━━━━━━━━━━━━

系统将自动推送此案件状态给用户。`
    };
  };

  const caseOverview = buildCaseOverview();

  const handleSend = async () => {
    setLoading(true);
    try {
      // 只发送 scheduledAt 和 immediate，后端自动构建 Case Overview
      await casePhaseAPI.sendPersonalPush(caseData.case_no, {
        scheduledAt: pushData.scheduledAt,
        immediate: pushData.immediate
      });
      message.success('案件推送已发送/预约');
      setPushData({ scheduledAt: null, immediate: true });
    } catch (err) {
      console.error('推送失败:', err);
      message.error('推送失败: ' + (err.response?.data?.detail || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title={<><UserOutlined /> 个人案件推送</>} style={{ marginBottom: 16 }}>
      <Form layout="vertical">
        {/* 显示 Case Overview 预览 */}
        <Form.Item label="案件信息预览 (Case Overview)">
          <div style={{ 
            background: '#f5f5f5', 
            padding: 16, 
            borderRadius: 8,
            fontFamily: 'monospace',
            whiteSpace: 'pre-wrap',
            fontSize: 13,
            lineHeight: 1.6
          }}>
            {caseOverview.overviewText}
          </div>
          <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
            <InfoCircleOutlined /> 将自动推送当前案件状态给用户
          </div>
        </Form.Item>
        
        <Form.Item label="发送方式">
          <Space>
            <Button
              type={pushData.immediate ? 'primary' : 'default'}
              icon={<PlayCircleOutlined />}
              onClick={() => setPushData(p => ({ ...p, immediate: true, scheduledAt: null }))}
            >
              立即发送
            </Button>
            <Button
              type={!pushData.immediate ? 'primary' : 'default'}
              icon={<ClockCircleOutlined />}
              onClick={() => setPushData(p => ({ ...p, immediate: false }))}
            >
              定时发送
            </Button>
          </Space>
        </Form.Item>
        {!pushData.immediate && (
          <Form.Item label="定时时间">
            <DatePicker
              showTime
              style={{ width: '100%' }}
              placeholder="选择推送时间"
              onChange={(date) => setPushData(p => ({ ...p, scheduledAt: date ? date.format('YYYY-MM-DD HH:mm:ss') : null }))}
            />
          </Form.Item>
        )}
        <Button 
          type="primary" 
          icon={<SendOutlined />} 
          onClick={handleSend} 
          loading={loading}
          size="large"
        >
          {pushData.immediate ? '立即推送案件状态' : '预约推送案件状态'}
        </Button>
      </Form>
    </Card>
  );
}

// ── 推送记录面板组件 ─────────────────────────────────────────
function PushTasksPanel({ caseNo }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [countdowns, setCountdowns] = useState({});

  const loadTasks = async () => {
    setLoading(true);
    try {
      const res = await pushTaskAPI.getByCase(caseNo);
      setTasks(res.data.tasks || []);
    } catch {
      message.error('加载推送记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
    const timer = setInterval(() => updateCountdowns(), 1000);
    return () => clearInterval(timer);
  }, [caseNo]);

  const updateCountdowns = () => {
    const now = dayjs();
    const newCountdowns = {};
    tasks.forEach(task => {
      if (task.status === 'pending' && task.scheduled_at) {
        const scheduled = dayjs(task.scheduled_at);
        const diff = scheduled.diff(now);
        if (diff > 0) {
          const minutes = Math.floor(diff / 60000);
          const seconds = Math.floor((diff % 60000) / 1000);
          newCountdowns[task.id] = `${minutes}分${seconds}秒`;
          if (minutes < 1) {
            newCountdowns[task.id] = { text: `${seconds}秒`, urgent: true };
          }
        } else {
          newCountdowns[task.id] = { text: '即将发送', urgent: true };
        }
      }
    });
    setCountdowns(newCountdowns);
  };

  const handleSendNow = async (taskId) => {
    try {
      await pushTaskAPI.sendNow(taskId);
      message.success('推送已发送');
      loadTasks();
    } catch (e) {
      message.error(e.response?.data?.detail || '发送失败');
    }
  };

  const handleRetry = async (taskId) => {
    try {
      await pushTaskAPI.retry(taskId);
      message.success('任务已重新安排');
      loadTasks();
    } catch (e) {
      message.error(e.response?.data?.detail || '重试失败');
    }
  };

  const handleCancel = async (taskId) => {
    try {
      await pushTaskAPI.cancel(taskId);
      message.success('任务已取消');
      loadTasks();
    } catch (e) {
      message.error(e.response?.data?.detail || '取消失败');
    }
  };

  const statusColors = {
    pending: 'orange',
    sent: 'blue',
    read: 'green',
    failed: 'red',
    cancelled: 'gray',
  };

  const statusLabels = {
    pending: '等待中',
    sent: '已发送',
    read: '已读',
    failed: '失败',
    cancelled: '已取消',
  };

  const columns = [
    {
      title: '阶段',
      dataIndex: 'phase',
      key: 'phase',
      render: (phase) => (
        <Tag color="blue">{phase} {PHASE_LABELS[phase]}</Tag>
      ),
    },
    {
      title: '推送类型',
      dataIndex: 'push_type',
      key: 'push_type',
      render: (type) => type === 'auto' ? '自动' : '手动',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={statusColors[status] || 'default'}>
          {statusLabels[status] || status}
        </Tag>
      ),
    },
    {
      title: '计划时间',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (v) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '倒计时',
      key: 'countdown',
      render: (_, record) => {
        if (record.status === 'pending' && countdowns[record.id]) {
          const cd = countdowns[record.id];
          return (
            <span style={{ color: cd.urgent ? '#ff4d4f' : '#faad14', fontWeight: cd.urgent ? 'bold' : 'normal' }}>
              {cd.text || cd}
            </span>
          );
        }
        return '-';
      },
    },
    {
      title: '实际发送',
      dataIndex: 'sent_at',
      key: 'sent_at',
      render: (v) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '已读时间',
      dataIndex: 'read_at',
      key: 'read_at',
      render: (v) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '失败原因',
      dataIndex: 'error_message',
      key: 'error_message',
      render: (v) => v ? <span style={{ color: 'red' }}>{v.substring(0, 50)}</span> : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          {record.status === 'pending' && (
            <>
              <Button 
                type="primary" 
                size="small" 
                onClick={() => handleSendNow(record.id)}
                loading={loading}
              >
                立即推送
              </Button>
              <Button 
                danger 
                size="small" 
                onClick={() => handleCancel(record.id)}
                loading={loading}
              >
                取消
              </Button>
            </>
          )}
          {record.status === 'failed' && (
            <Button 
              type="primary" 
              size="small" 
              onClick={() => handleRetry(record.id)}
              loading={loading}
            >
              重试
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>共 {tasks.length} 条推送记录</span>
        <Button type="primary" onClick={loadTasks} loading={loading}>
          刷新
        </Button>
      </div>
      <Table 
        dataSource={tasks} 
        columns={columns} 
        rowKey="id" 
        size="small"
        pagination={{ pageSize: 10 }}
        loading={loading}
      />
    </div>
  );
}

// ── 主页面组件 ─────────────────────────────────────────
function CaseDetail() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [caseData, setCaseData] = useState(null);
  const [history, setHistory] = useState([]);
  const [evidences, setEvidences] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedPhase, setSelectedPhase] = useState(null);
  const [activeTab, setActiveTab] = useState('info');

  const load = async () => {
    setLoading(true);
    try {
      const [cRes, hRes, eRes, aRes] = await Promise.all([
        casesAPI.getOne(caseId),
        casePhaseAPI.getHistory(caseId).catch(() => ({ data: { history: [] } })),
        casePhaseAPI.getEvidences(caseId).catch(() => ({ data: { evidences: [] } })),
        agentsAPI.getAll().catch(() => ({ data: { agents: [] } })),
      ]);
      const data = cRes.data;
      setCaseData(data);
      setHistory(hRes.data.history || []);
      setEvidences(eRes.data.evidences || []);
      setAgents(aRes.data.agents || []);
      // 默认选中实际阶段
      setSelectedPhase(data.status || 'P1');
    } catch { message.error('加载失败'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [caseId]);

  const handleAdvance = async (data) => {
    try {
      await casePhaseAPI.advance(caseId, data);
      message.success(`已推进至 ${data.new_phase}`);
      load();
    } catch (e) { message.error(e.response?.data?.detail || '推进失败'); }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  if (!caseData) return <div style={{ padding: 24 }}>案件不存在</div>;

  const actualPhase = caseData.status || 'P1';

  const evidenceCols = [
    { title: '文件名', dataIndex: 'file_name', key: 'file_name' },
    { title: '类型', dataIndex: 'file_type', key: 'file_type' },
    { title: '上传时间', dataIndex: 'uploaded_at', key: 'uploaded_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
  ];

  const historyCols = [
    { title: '旧阶段', dataIndex: 'old_status', key: 'old_status' },
    { title: '新阶段', dataIndex: 'new_status', key: 'new_status', render: v => <Tag color="blue">{v}</Tag> },
    { title: '操作人', dataIndex: 'changed_by', key: 'changed_by' },
    { title: '时间', dataIndex: 'changed_at', key: 'changed_at', render: v => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '备注', dataIndex: 'notes', key: 'notes' },
  ];

  return (
    <div>
      {/* 顶部导航 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cases')}>返回案件列表</Button>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>案件详情</h1>
        <Tag color="blue" style={{ fontSize: 14 }}>{actualPhase}</Tag>
        <span style={{ color: colors.grayMedium }}>{PHASE_LABELS[actualPhase]}</span>
      </div>

      {/* P1-P12 可点击进度条 */}
      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: '16px' }}>
        <PhaseProgressBar
          currentPhase={selectedPhase}
          actualPhase={actualPhase}
          onSelect={setSelectedPhase}
          caseStatus={caseData.status}
        />
      </Card>

      {/* 主内容区 - 使用独立Tab组件解决切换问题 */}
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card style={{ marginBottom: 16 }}>
            <Tabs activeKey={activeTab} onChange={setActiveTab} type="card">
              <TabPane tab="基本信息" key="info">
                <Descriptions bordered column={2} size="small">
                  <Descriptions.Item label="案件编号">{caseData.case_no}</Descriptions.Item>
                  <Descriptions.Item label="渠道"><Tag color="blue">{caseData.channel}</Tag></Descriptions.Item>
                  <Descriptions.Item label="用户ID">{caseData.tg_user_id}</Descriptions.Item>
                  <Descriptions.Item label="用户名">{caseData.tg_username || '-'}</Descriptions.Item>
                  <Descriptions.Item label="涉案金额">{caseData.amount ? `${caseData.amount} ${caseData.coin}` : '-'}</Descriptions.Item>
                  <Descriptions.Item label="区块链">{caseData.chain_type || '-'}</Descriptions.Item>
                  <Descriptions.Item label="钱包地址" span={2}>{caseData.wallet_addr || '-'}</Descriptions.Item>
                  <Descriptions.Item label="交易哈希" span={2}>{caseData.tx_hash || '-'}</Descriptions.Item>
                  <Descriptions.Item label="风险评分">{caseData.risk_score || '-'}</Descriptions.Item>
                  <Descriptions.Item label="风险标签">{caseData.risk_label || '-'}</Descriptions.Item>
                  <Descriptions.Item label="探员代号">{caseData.agent_code || '-'}</Descriptions.Item>
                  <Descriptions.Item label="提交时间">{caseData.created_at ? new Date(caseData.created_at).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
                  <Descriptions.Item label="内部备注" span={2}>{caseData.admin_notes || '-'}</Descriptions.Item>
                </Descriptions>
              </TabPane>

              <TabPane tab="阶段操作" key="phase">
                <PhaseOperationPanel
                  caseData={caseData}
                  selectedPhase={selectedPhase}
                  actualPhase={actualPhase}
                  onAdvance={handleAdvance}
                  agents={agents}
                />
              </TabPane>

              <TabPane tab={`证据 (${evidences.length})`} key="evidence">
                <Table dataSource={evidences} columns={evidenceCols} rowKey="id" size="small" pagination={false} />
              </TabPane>

              <TabPane tab="阶段历史" key="history">
                <Table dataSource={history} columns={historyCols} rowKey="id" size="small" pagination={false} />
              </TabPane>

              <TabPane tab="自动推送" key="auto">
                <AutoPushSettings caseData={caseData} />
              </TabPane>

              <TabPane tab="个人推送" key="personal">
                <PersonalPush caseData={caseData} />
              </TabPane>

              <TabPane tab="推送记录" key="push">
                <PushTasksPanel caseNo={caseId} />
              </TabPane>
            </Tabs>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="安全联络 1v1" style={{ height: 'calc(100vh - 300px)', minHeight: 400 }}>
            <ChatPanel caseNo={caseId} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default CaseDetail;
