package com.swir.maxkompilator.fixture;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        String marker = getString(com.swir.maxkompilator.fixture.R.string.runtime_marker);
        if (!"MAXKOMPILATOR_ANDROID_RUNTIME_OK".equals(marker)) {
            throw new IllegalStateException("Compiled Android resource did not match");
        }
        TextView view = new TextView(this);
        view.setText(marker);
        view.setTextSize(22);
        view.setPadding(32, 64, 32, 32);
        setContentView(view);
        Log.i("MaxkompilatorFixture", marker);
    }
}
