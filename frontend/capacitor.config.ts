import type { CapacitorConfig } from "@capacitor/cli"

const config: CapacitorConfig = {
  appId: "com.weis.tquant",
  appName: "维斯量化交易",
  webDir: "dist-native",
  bundledWebRuntime: false,
  server: {
    androidScheme: "https",
    allowNavigation: [
      "weisilianghua.cloud",
      "www.weisilianghua.cloud"
    ]
  },
  plugins: {
    CapacitorHttp: {
      enabled: true
    },
    SplashScreen: {
      launchAutoHide: true,
      backgroundColor: "#f4f5ef",
      showSpinner: false
    },
    StatusBar: {
      style: "DARK",
      backgroundColor: "#f4f5ef"
    }
  }
}

export default config
