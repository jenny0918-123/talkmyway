<template>
  <el-card class="prompter-card" shadow="never">
    <template #header>
      <div class="prompter-header">
        <div>
          <el-text size="large" class="prompter-title">提词器</el-text>
          <el-text class="prompter-subtitle">输入稿件，调整速度与字号，开始滚动。</el-text>
        </div>
        <el-button-group>
          <el-button :type="isRunning ? 'primary' : 'default'" @click="toggleRun">
            {{ isRunning ? '暂停' : '开始' }}
          </el-button>
          <el-button @click="resetScroll">回到顶部</el-button>
        </el-button-group>
      </div>
    </template>

    <div class="prompter-controls">
      <div class="control-item">
        <el-text>滚动速度</el-text>
        <el-slider v-model="speed" :min="10" :max="200" :step="5" />
        <el-input-number v-model="speed" :min="10" :max="200" :step="5" controls-position="right" />
      </div>
      <div class="control-item">
        <el-text>字号</el-text>
        <el-slider v-model="fontSize" :min="20" :max="72" :step="2" />
        <el-input-number v-model="fontSize" :min="20" :max="72" :step="2" controls-position="right" />
      </div>
      <div class="control-item">
        <el-text>行距</el-text>
        <el-slider v-model="lineHeight" :min="1.2" :max="2.4" :step="0.1" />
        <el-input-number v-model="lineHeight" :min="1.2" :max="2.4" :step="0.1" controls-position="right" />
      </div>
      <div class="control-item switches">
        <el-switch v-model="mirror" active-text="镜像" inactive-text="正常" />
        <el-switch v-model="dimBackground" active-text="暗色背景" inactive-text="亮色背景" />
      </div>
    </div>

    <el-row :gutter="24" class="prompter-body">
      <el-col :span="8">
        <el-text class="section-label">稿件内容</el-text>
        <el-input
          v-model="script"
          type="textarea"
          :rows="18"
          placeholder="在这里输入你的演讲稿或台词..."
        />
        <div class="helper-actions">
          <el-button size="small" @click="loadSample">填入示例</el-button>
          <el-button size="small" type="danger" plain @click="clearScript">清空</el-button>
        </div>
      </el-col>
      <el-col :span="16">
        <el-text class="section-label">提词预览</el-text>
        <div
          ref="scrollContainer"
          class="prompter-preview"
          :class="{ dim: dimBackground }"
        >
          <div class="prompter-text" :style="prompterStyle">
            <p v-for="(line, index) in formattedLines" :key="index">{{ line }}</p>
          </div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script>
export default {
  name: 'TeleprompterPanel',
  data() {
    return {
      script: '欢迎使用提词器。\n\n在左侧输入你的稿件，点击开始即可滚动。',
      speed: 40,
      fontSize: 40,
      lineHeight: 1.6,
      mirror: false,
      dimBackground: true,
      isRunning: false,
      rafId: null,
      lastTimestamp: null,
      scrollTop: 0,
    }
  },
  computed: {
    formattedLines() {
      return this.script.split('\n')
    },
    prompterStyle() {
      return {
        fontSize: `${this.fontSize}px`,
        lineHeight: this.lineHeight,
        color: this.dimBackground ? '#f5f5f5' : '#1a1a1a',
        transform: this.mirror ? 'scaleX(-1)' : 'none',
      }
    },
  },
  watch: {
    script() {
      this.resetScroll()
    },
  },
  beforeUnmount() {
    this.stopScroll()
  },
  methods: {
    toggleRun() {
      if (this.isRunning) {
        this.stopScroll()
        return
      }
      this.isRunning = true
      this.lastTimestamp = null
      this.rafId = requestAnimationFrame(this.stepScroll)
    },
    stepScroll(timestamp) {
      if (!this.isRunning) {
        return
      }
      if (!this.lastTimestamp) {
        this.lastTimestamp = timestamp
      }
      const delta = timestamp - this.lastTimestamp
      const scrollContainer = this.$refs.scrollContainer
      if (!scrollContainer) {
        return
      }
      const maxScroll = scrollContainer.scrollHeight - scrollContainer.clientHeight
      this.scrollTop = Math.min(this.scrollTop + (this.speed * delta) / 1000, maxScroll)
      scrollContainer.scrollTop = this.scrollTop
      this.lastTimestamp = timestamp
      if (this.scrollTop >= maxScroll) {
        this.stopScroll()
        return
      }
      this.rafId = requestAnimationFrame(this.stepScroll)
    },
    stopScroll() {
      this.isRunning = false
      if (this.rafId) {
        cancelAnimationFrame(this.rafId)
        this.rafId = null
      }
    },
    resetScroll() {
      this.stopScroll()
      this.scrollTop = 0
      const scrollContainer = this.$refs.scrollContainer
      if (scrollContainer) {
        scrollContainer.scrollTop = 0
      }
    },
    loadSample() {
      this.script =
        '大家好，欢迎来到今天的分享。\n\n第一部分，我们将介绍产品亮点。\n第二部分，我们会演示真实案例。\n最后欢迎提问，谢谢大家。'
    },
    clearScript() {
      this.script = ''
    },
  },
}
</script>

<style scoped>
.prompter-card {
  width: 100%;
}

.prompter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.prompter-title {
  font-weight: 600;
  margin-right: 12px;
}

.prompter-subtitle {
  color: #6b7280;
}

.prompter-controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.control-item.switches {
  justify-content: center;
  gap: 16px;
}

.prompter-body {
  margin-top: 8px;
}

.section-label {
  display: inline-block;
  margin-bottom: 8px;
  font-weight: 500;
}

.helper-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.prompter-preview {
  height: 520px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  overflow-y: auto;
  padding: 24px;
  transition: background 0.2s ease;
}

.prompter-preview.dim {
  background: #0f172a;
}

.prompter-text {
  min-height: 100%;
  white-space: pre-wrap;
}

.prompter-text p {
  margin: 0 0 16px;
}
</style>
