<template>

  <el-backtop/>

  <el-container id="out">

    <el-header class="main-header">
      <el-text class="title-text" size="large">SpokenGPT</el-text>
      <div class="header-actions">
        <el-button-group>
          <el-button :type="activeView === 'chat' ? 'primary' : 'default'" @click="activeView = 'chat'">
            口语练习
          </el-button>
          <el-button :type="activeView === 'prompter' ? 'primary' : 'default'" @click="activeView = 'prompter'">
            提词器
          </el-button>
        </el-button-group>
      </div>
      <div class="avatar">
        <el-input v-model="name" style="display:inline;" placeholder="Your name..."/>
        <el-avatar style="margin-left: 16px"> {{ getFirstChar(name) }}</el-avatar>
      </div>
    </el-header>

    <el-container id="row" style="height: calc(100% - 60px);">

      <el-aside id="list">
        <el-scrollbar>
        <el-button size="large" id="add" @click="dialogVisible = true">
          <Plus class="my-svg" style="margin-right: 12px"/>
          <el-text class="white-text">新建会话</el-text>
        </el-button>

        <el-dialog v-model="dialogVisible" title="选择模式">
          <div class="dialog-footer" style="margin-bottom: 20px">
<!--              <el-button type="primary" @click="newChat(1)">-->
              <el-button type="primary" @click="this.showForm=1">
                日常口语
              </el-button>
            <!--              <el-button type="primary" @click="newChat(2)">-->
              <el-button type="primary" @click="this.showForm=2">
                雅思口语
              </el-button>
            </div>

<!--          日常-->
          <el-form v-if="showForm === 1">
            <el-form-item label="Level">
              <el-select class="m-2" placeholder="Select" v-model="dailySelect">
                <el-option
                    v-for="item in dailyLevel"
                    :key="item"
                    :label="item"
                    :value="item"
                />
              </el-select>
            </el-form-item>
          </el-form>

<!--          ielts-->
          <el-form v-if="showForm === 2">
            <el-form-item label="Part1 Topic1">
              <el-cascader
                  v-model="part1Select1"
                  :options="part1Option"
                  :props="props"
                  placeholder="Select"
              />
            </el-form-item>

            <el-form-item label="Part1 Topic2">
              <el-cascader
                  v-model="part1Select2"
                  :options="part1Option"
                  :props="props"
                  placeholder="Select"
              />
            </el-form-item>

            <el-form-item label="Part2 Topic">
              <el-select class="m-2" placeholder="Select" v-model="part2Select">
                <el-option
                    v-for="(value, key) in part2Option"
                    :key="key"
                    :label="key"
                    :value="value"
                />
              </el-select>
            </el-form-item>
          </el-form>

          <template #footer>
            <el-button type="primary" @click="newChat(showForm)" :loading="submitLoading">提交</el-button>
          </template>
        </el-dialog>

        <el-menu id="menu">
          <el-tooltip
              placement="right"
              v-for="i in history.slice().reverse()"
              :key="i.id"
              :content="describe(i.level, i.mode)"
              raw-content
              offset=24
              class="multiline-tooltip"
          >
            <el-menu-item @click="enterChat(i.id, i.mode)">
              <ChatSquare class="my-svg" style="margin-right: 12px"/>
              <el-text style="color: white;margin-right: 8px;">{{ i.time }}</el-text>
              <el-tag class="ml-1" size="small" :type="i.mode == 3 ? 'info' : ''" >
                {{ i.mode == 1 ? '日常口语' : '雅思口语' }}
              </el-tag>
              <Delete class="my-svg" style="margin-left: auto" @click="deleteHistory(i.id)"/>
            </el-menu-item>
          </el-tooltip>
        </el-menu>
        </el-scrollbar>
      </el-aside>

      <el-main id="chat">
        <el-scrollbar v-if="activeView === 'chat'">
        <div id="chatUI" v-if="chatMode">

          <el-dialog v-model="dialogRecordVisible" title="正在录制...">
            <el-text size="large" style="font-size: 28px">{{ recorder && recorder.duration.toFixed(2) }} s </el-text>
            <template #footer>
                <span class="dialog-footer">
                  <el-button type="primary" @click="finishRecording">
                    结束
                  </el-button>
                  <el-button type="danger" @click="stopRecording">
                    取消
                  </el-button>
                </span>
            </template>
          </el-dialog>


          <div class="fixed-button">
            <el-button type="primary" size="large" @click="startRecording" :loading="loading">
              开始录制</el-button>
<!--            <el-button type="warning" size="large" @click="endChat" v-if="chatMode == 2">结束会话</el-button>-->
          </div>

          <div class="statement" v-for="(i, index) in statement" :key="i.id">
            <div class="left-column">
              <el-avatar shape="square" style="margin-right: 16px">
                {{ i.from_gpt ? 'GPT' : getFirstChar(name) }}
              </el-avatar>
            </div>
            <div class="right-column">
              <text style="margin-bottom: 20px;font-size: 18px">{{ i.content }}</text>
              <audio controls ref="audioElements" :src="urlFill(i.audio)" crossorigin="anonymous">您的浏览器不支持audio标签.</audio>
                <el-row v-if="i.from_gpt === 0">
                  <el-col :span="6">
                    <el-statistic title="发音评分" :value="JSON.parse(i.score).PronScore" />
                  </el-col>
                  <el-col :span="6">
                    <el-statistic title="准确性评分" :value="JSON.parse(i.score).AccuracyScore" />
                  </el-col>
                  <el-col :span="6">
                    <el-statistic title="流畅性评分" :value="JSON.parse(i.score).FluencyScore" />
                  </el-col>
                  <el-col :span="6">
                    <el-statistic title="完整性评分" :value="JSON.parse(i.score).CompletenessScore" />
                  </el-col>
                </el-row>
                <div v-if="i.from_gpt === 0">
                <el-button round style="margin-right: 20px;margin-top: 20px;margin-bottom: 10px"
                    @click="getAssess(index, i.content)">让GPT评价</el-button>
                  <br /><el-text size="large" style="width: 50px">{{ getAssessValue(index) }}</el-text>
                </div>

              <el-divider/>
            </div>
          </div>

        </div>

        <div id="emptyUI" v-else>
          <el-empty description="在左侧新建会话，或查看历史会话"/>
        </div>
        </el-scrollbar>
        <div v-else class="prompter-view">
          <Teleprompter />
        </div>
      </el-main>
    </el-container>

  </el-container>

</template>

<!--<script setup>-->
<!--  import { ref } from 'vue'-->
<!--  const dialogVisible = ref(false)-->
<!--</script>-->

<script>
import {Delete, ChatSquare, Plus} from "@element-plus/icons-vue";
import axios from "axios";
import Recorder from 'js-audio-recorder';
import {part2TopicPool, dailyLevel} from '../src/assets/js/pool'
import part1TopicPool from '../public/part1.json'
import Teleprompter from "./components/Teleprompter.vue";

export default {
  components: {Delete, ChatSquare, Plus, Teleprompter},
  data() {
    return {
      activeView: 'chat',
      part1Option: part1TopicPool,
      part2Option: part2TopicPool,
      // part2Option: part2TopicPool,
      props: {value: 'id', label: 'id', children: 'children', emitPath: false},
      dailyLevel: dailyLevel,
      dailySelect: null,
      part1Select1: null,
      part1Select2: null,
      part2Select: null,
      showForm: 0,  // 显示表单 0: Empty 1: 日常 2:ielts
      loading: false,
      recorder: null,
      dialogVisible: false,
      dialogRecordVisible: false,
      name: 'Alice',
      chatMode: 0,  // 0:空 1:会话中 2:ielts-未结束 3:ielts-已结束
      history: [],
      statement: [],
      cur_id: 0,
      chunks: [],  // 录音
      level: '',
      submitLoading: false,
    };
  },
  methods: {
    getHistory() {
      axios.get('http://127.0.0.1:5000/history')
          .then(response => {
            this.history = response.data
          })
          .catch(error => {
            console.error(error);
          });
    },
    getFirstChar(value) {
      if (typeof value === 'string') {
        return value.charAt(0);
      }
      return value;
    },
    newChat(spokenMode) {
      this.submitLoading = true
      if (spokenMode === 1 && !this.dailySelect) {
        return
      }
      if (spokenMode === 2 && (!this.part1Select1 || !this.part1Select2 || !this.part2Select)) {
        return
      }

      // spokenMode: 1.日常口语 2.雅思口语
      let formData = new FormData();
      formData.append('username', this.name)
      if (spokenMode === 1) {
        formData.append('daily', this.dailySelect);
      }
      if (spokenMode === 2) {
        formData.append('part1topic1', this.part1Select1)
        formData.append('part1topic2', this.part1Select2)
        formData.append('part2', this.part2Select)
      }

      axios.post(`http://127.0.0.1:5000/history/${spokenMode}`, formData)
          .then(response => {
            if (response.data.msg === 'success') {
              this.dialogVisible = false
              this.cur_id = response.data.id
              this.getHistory()
              this.submitLoading = false
              this.enterChat(this.cur_id, spokenMode)
            }
          })
          .catch(err => {
            console.log(err)
          })
    },
    // endChat() {
    //   axios.put(`http://127.0.0.1:5000/history/${this.cur_id}`)
    //       .then(response => {
    //         if (response.data.msg === 'success') {
    //           this.chatMode = 3
    //           this.getHistory()
    //         }
    //       })
    // },
    startRecording() {  // 开始录音
      this.dialogRecordVisible = true
      Recorder.getPermission()
          .then(() => {
            console.log('开始录音')
            this.recorder.start()
                .then(() => {
                  // 开始录音
                  this.loading = true
                })
                .catch(error => {
                  console.log(error);
                })
          })
          .catch(error => {
            console.log(`${error.name} : ${error.message}`)
          })
    },
    finishRecording() {
      console.log('finish');
      this.dialogRecordVisible = false;

      this.recorder.stop();
      const formData = new FormData();
      formData.append('audio', this.recorder.getWAVBlob());

      axios.post(`http://127.0.0.1:5000/gpt/${this.cur_id}`, formData, {
        headers: {'Content-Type': 'multipart/form-data'}
      })
          .then(() => {
            console.log('录音已发送到后端');
            axios.get(`http://127.0.0.1:5000/chat/${this.cur_id}`)
                .then(response => {
                  // console.log('not loading');
                  this.loading = false;
                  this.statement = response.data;
                  this.$nextTick(() => {
                    const bottomElements = this.$refs.audioElements
                    const bottom = bottomElements[bottomElements.length - 1];
                    bottom.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    this.playLatest();
                  })
                })
                .catch(error => {
                  console.error(error);
                });

            this.recorder.destroy();
            this.recorder = new Recorder({
              sampleBits: 16,
              sampleRate: 16000,
              numChannels: 1
            });
          })
          .catch(error => {
            console.error('发送录音时发生错误', error);
          });
    },
    stopRecording() {
      this.dialogRecordVisible = false;
      this.recorder.destroy();
      this.recorder = new Recorder({
        sampleBits: 16,
        sampleRate: 16000,
        numChannels: 1
      });
      this.loading = false
    },
    urlFill(a) {
      // console.log(a)
      return `http://127.0.0.1:5000/${a}`
    },
    deleteHistory(id) {
      axios.delete(`http://127.0.0.1:5000/history/${id}`)
          .then(() => {
            this.getHistory()
          })
          .catch(error => {
            console.error(error);
          });
    },
    enterChat(id, spokenMode) {
      axios.get(`http://127.0.0.1:5000/chat/${id}`)
          .then(response => {
            this.statement = response.data
            this.chatMode = spokenMode
            this.cur_id = id
          })
          .catch(error => {
            console.error(error);
          });
    },
    describe(level, spokenMode) {
      let levelObj = JSON.parse(level)
      let text = ''
      if (spokenMode === 1) {
        text = `难度：${levelObj.daily}`
      } else if (spokenMode === 2 || spokenMode === 3) {
        text = `Part 1 话题1: ${levelObj.part1topic1} \nPart 1 话题2: ${levelObj.part1topic2} \nPart 2 话题: ${levelObj.part2}`
      }
      return `<el-text style="white-space: pre-wrap; font-size: 14px">${text}</el-text>`
    },
    getAssess(index, content) {
      let formData = new FormData
      formData.append('content', content)
      axios.post('http://127.0.0.1:5000/gpt/assess', formData)
          .then(response => {
            if (response.data.msg === 'success') {
              this.statement[index].assess = response.data.assess
            }
          })
    },
    playLatest() {
      const audioElements = this.$refs.audioElements;
      const lastAudioElement = audioElements[audioElements.length - 1];

      // 音频上下文
      const AudioContext = window.AudioContext
      const audioContext = new AudioContext();
      audioContext.crossOrigin = "anonymous";
      const track = audioContext.createMediaElementSource(lastAudioElement);
      track.connect(audioContext.destination)
      lastAudioElement.play()
    },
  },
  computed: {
    getAssessValue() {
      return (index) => this.statement[index].assess || '';
    }
  },
  mounted() {
    this.getHistory()
    this.recorder = new Recorder({
      sampleBits: 16, // 采样位数，支持 8 或 16，默认是16
      sampleRate: 16000, // 采样率，支持 11025、16000、22050、24000、44100、48000
      numChannels: 1 // 声道，支持 1 或 2， 默认是1
    })
  },
}

</script>

<style scoped>
.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-actions {
  flex: 1;
  display: flex;
  justify-content: center;
}

.prompter-view {
  padding: 24px;
}
</style>
